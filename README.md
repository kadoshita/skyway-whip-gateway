# skyway-whip-gateway

SkyWayのSFUにWHIPで映像を送るためのアプリケーション

## **❗注意**

これはSkyWayのSDKとは無関係の非公式の実装です。
動作は保証しておらず、SkyWayの仕様変更により動かなくなる可能性があります。
また、コードや動作についての質問などはSkyWayのサポートへの連絡は行わず、本リポジトリのissueに投稿してください。

## 実装済みの機能

- OBSからWHIPで受信した映像のSFU BotによるForwarding

## 未実装の機能(抜粋)

- OBSからWHIPで受信した音声のSFU BotによるForwarding
- Simulcast
- STUN / TURNの利用
- 再接続処理
- エラーハンドリング
- SkyWay Auth Tokenの更新
- Metadataの取得・更新

## 利用方法

### セットアップ

```sh
$ git clone git@github.com:kadoshita/skyway-whip-gateway.git
$ cd skyway-whip-gateway
$ python -m venv .
$ source bin/activate
$ python -m pip install -r requirements.txt
$ patch -d ./lib/path/to/aiortc/ -p1 < ./patch/set_cipher_list.patch # 重要!! パスは環境に合わせて変更してください
$ cd src
$ python main.py
```

### Subscriber側

1. Webアプリケーションの起動
```shell
$ cd skyway-whip-gateway/public
$ cp ../.env .
$ npm install
$ npm start
```
2. Channelの作成
   1. [http://localhost:1234/](http://localhost:1234/)にアクセスする
   2. Startボタンをクリックする
   3. Create Channelボタンをクリックする
   4. Join Channelボタンをクリックする
   5. Channel IDをコピーする
3. OBSで配信を開始
4. SFU BotからのPublicationのSubscribe
   1. コンソールに出力されたSFU BotからのPublicationのIDをコピーする
   2. 「Publication ID:」のテキストボックスにPublicationのIDをペーストする
   3. Subscribe Mediaボタンをクリックする

### OBSの設定

1. 設定→配信を開く
2. サービスとして「WHIP」を選択する
3. サーバーのアドレスとして「[http://localhost:8080/whip](http://localhost:8080/whip)」を設定する
4. OKを押して閉じる

- 「配信開始」ボタンを押せば、WHIPでの配信が始まります。
- skyway-whip-gatewayを起動している端末でChannel IDの入力を求められるため、Subscriber側の手順の2.でコピーしたChannel IDを貼り付けてEnterを押す

## パッチについて

- `patch/set_cipher_list.patch` で、aiortcが利用する暗号スイートを変更しています。これは、以下の理由によるものです。
    - OBSでは、WebRTCのライブラリとしてlibdatachannelを利用しており、OBSで利用されているlibdatachannelはMbed TLSを利用する設定でビルドされています。
    - Mbed TLSは、v3.5.0の時点で、Client Helloのフラグメンテーションをサポートしていません。
      - https://github.com/Mbed-TLS/mbedtls/blob/v3.5.0/library/ssl_tls12_server.c#L1085
    - そのため、利用可能な暗号の数が多い場合にClient Helloのサイズが大きくなり、フラグメンテーションが発生し、接続時にエラーとなります。
    - これを防ぐために、暗号スイートを明示的に設定し、フラグメンテーションが発生しないサイズに抑えています。
    - なお、libdatachannelをOpenSSLを利用する設定でビルドした場合は、この問題が発生しないことを確認しています。

## 動作環境

- macOS Ventura 13.6
- OBS Studio 30.0.0-rc1
- Python 3.10.8
- pip 22.2.2
- Node.js v18.4.0
