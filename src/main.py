import logging
import settings
import jwt
import asyncio
import websockets
import uuid
import time
from aiohttp import web
from aiohttp_middlewares import cors_middleware
from rtc_api_client import RtcApiClient
from sfu_api_client import SfuApiClient
from mediasoup_client import MediasoupClient
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer, MediaRelay

logger = logging.getLogger('whip')
logging.getLogger().setLevel(logging.INFO)

token = jwt.encode(
    {
        "jti": str(uuid.uuid4()),
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
        "scope": {
            "app": {
                "id": settings.APP_ID,
                "turn": True,
                "actions": ["read"],
                "channels": [
                    {
                        "id": "*",
                        "name": "*",
                        "actions": ["write"],
                        "members": [
                            {
                                "id": "*",
                                "name": "*",
                                "actions": ["write"],
                                "publication": {"actions": ["write"]},
                                "subscription": {"actions": ["write"]},
                            }
                        ],
                        "sfuBots": [
                            {
                                "actions": ["write"],
                                "forwardings": [{"actions": ["write"]}],
                            }
                        ],
                    }
                ],
            }
        },
    },
    settings.SECRET_KEY,
    algorithm="HS256",
)

class WHIP:
    def __init__(self):
        self._pc = None

    async def whip(self, request):
        if request.content_type != 'application/sdp':
            return web.Response(status=400)
        if self._pc is not None:
            return web.Response(status=400)

        offerText = await request.text()

        logger.info(offerText)
        offer = RTCSessionDescription(sdp=offerText, type='offer')

        self._pc = RTCPeerConnection()

        @self._pc.on('iceconnectionstatechange')
        async def on_iceconnectionstatechange():
            logger.info('ICE connection state is %s', self._pc.iceConnectionState)
            if self._pc.iceConnectionState == 'failed':
                await self._pc.close()

        @self._pc.on('track')
        async def on_track(track):
            logger.info('Track %s received', track.kind)

            if track.kind == 'video':
                async with websockets.connect(
                    "wss://rtc-api.skyway.ntt.com:443/ws", subprotocols=[token]
                ) as websocket:
                    rtc_api_client = RtcApiClient(websocket, token, settings.APP_ID)
                    sfu_api_client = SfuApiClient(token, settings.APP_ID)
                    channel_id = input("channel_id: ")

                    channel = await rtc_api_client.get_channel(channel_id)
                    print(channel)

                    member = await rtc_api_client.join_channel(channel_id)
                    print(member)
                    member_id = member["result"]["memberId"]

                    await asyncio.sleep(1)

                    publication = await rtc_api_client.publish_stream(channel_id, member_id)
                    print(publication)
                    publication_id = publication["result"]["id"]

                    bot = await sfu_api_client.create_bot(channel_id)
                    print(bot)
                    bot_id = bot["id"]

                    forwarding = await sfu_api_client.start_forwarding(
                        member_id, publication_id, bot_id, "Video", 1
                    )

                    if "broadcasterTransportId" not in forwarding:
                        raise Exception("broadcasterTransportId is not found")

                    if "forwardingId" not in forwarding:
                        raise Exception("forwardingId is not found")

                    mediasoup_client = MediasoupClient(
                        sfu_api_client,
                        bot_id,
                        forwarding["broadcasterTransportId"],
                        forwarding["forwardingId"],
                    )

                    if "rtpCapabilities" in forwarding:
                        await mediasoup_client.load(forwarding["rtpCapabilities"])

                    if "broadcasterTransportOptions" in forwarding:
                        await mediasoup_client.create_send_transport(
                            forwarding["broadcasterTransportOptions"]
                        )

                    async def on_stream_subscribed_callback(data):
                        while True:
                            await asyncio.sleep(1)
                            response = await sfu_api_client.confirm_subscription(
                                forwarding["forwardingId"],
                                data["params"]["data"]["subscription"]["id"],
                                forwarding["identifierKey"],
                            )
                            if (
                                "message" in response
                                and response["message"] == "IdentifierKey is invalid"
                            ):
                                continue
                            else:
                                break

                    await rtc_api_client.on_stream_subscribed(on_stream_subscribed_callback)

                    await mediasoup_client.produce(track)

                    await asyncio.sleep(3600)

            @track.on('ended')
            async def on_ended():
                logger.info('Track %s ended', track.kind)

        await self._pc.setRemoteDescription(offer)

        answer = await self._pc.createAnswer()
        await self._pc.setLocalDescription(answer)

        logger.info(answer.sdp)

        return web.Response(
            status=201,
            content_type='application/sdp',
            headers={'Access-Control-Allow-Origin': '*', 'Access-Controll-Allow-Header': '*', 'Location': '/whip'},
            text=answer.sdp
        )

    async def stop_whip(self, request):
        if self._pc:
            await self._pc.close()
            self._pc = None

        return web.Response(status=200)

if __name__ == "__main__":
    app = web.Application(middlewares=[cors_middleware(allow_all=True)])
    whip = WHIP()
    app.router.add_post('/whip', whip.whip)
    app.router.add_delete('/whip', whip.stop_whip)

    web.run_app(app, port=8080, access_log=logger)
