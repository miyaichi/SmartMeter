# SmartMeter

M5StickC と BP35A1、Wi-SUN Hat を組み合わせたスマートメーターモニタ

![Smart Meter Monitor](https://user-images.githubusercontent.com/129797/83958481-5198d300-a8ad-11ea-9cba-ddc13c4ae0b1.jpg)

2016 年からアナログの電力量計からデジタルのスマートメーターへのリプレイスが始まっています。スマートメーターへのアクセスは電力会社が利用する A ルートの他に、申し込めば誰でも使える B ルートが用意されており、申し込みをすれば無料で自宅のスマートメーター にアクセスできます。ただ、スマートメータとの通信は、Wi-SUN(Wireless Smart Utility Network : 特定小電力無線)経由となるため、対応した通信機器が必要になります。

簡易にやるのであれば、[Nature Remo E/Nature Remo E lite](https://nature.global/jp/nature-remo-e)を購入するだけで、スマホでモニタリングやコントロールができるようになるのですが、やっぱり自分でやって見たいよねと言うことでプロジェクトをはじめました。

調べてみると、先人はたくさんおられ、特に[M5StickC で家庭用スマートメーターをハックする！](https://kitto-yakudatsu.com/archives/7206)という、M5StickC を使った完成度の高いものが見つかりました。

さっそく、Visual Studio Code で M5StickC の micropython 環境を作り、試したところ、あっという間にスマートメーター の情報が取得できましたが、やはり、車輪は再発明するもの(笑)、新たにコードを書くことにしました。

## Feature

- 現在の電流、電力の情報を表示します。
- 今月（検針日を起点）の電力量を表示します。
- 今月の電気料金を計算し表示します。また、電気料金計算方法はカスタマイズが可能です。
- A ボタンでで画面の上下をコントロールできます。
- Ambient に電流、電力、電力量、電気料金の情報を送信できます。

## B Route Service

まずは、B ルートサービスの申し込みが必要です、東京電力であれば、[電力メーター情報発信サービス（B ルートサービス）](https://www.tepco.co.jp/pg/consignment/liberalization/smartmeter-broute.html)から、他の電力会社も同様のサービスをしていますので、契約している電力会社を確認してください。

申し込みが完了すると、認証 ID とパスワードが送られてきますので、これでスマートメーターアクセスできるようになります。

## Hardeware

M5StickC と BP35A1、BP35A1 をいい感じで M5StickC 用の HAT にしてくれる Wi-Sun HAT キットを用意します。

- [M5StickC](https://www.switch-science.com/catalog/5517/)
- [特定省電力無線モジュール BP35A1](https://jp.rs-online.com/web/p/wlan-modules/8273170/)
- [M5StickC 用「Wi-SUN HAT」キット](https://booth.pm/ja/items/1650727)

BP35A1 は 7,500-12,000 円ぐらいするので、総額では Nature Remo E Lite 12,800 円といい勝負になってしまうのが課題です。

## Software

### Clone this repository

```bash
git clone https://github.com/miyaichi/SmartMeter.git
cd SmartMeter
```

### Download Ambient module

```bash
curl -o ambient.py https://raw.githubusercontent.com/AmbientDataInc/ambient-python-lib/master/ambient.py
```

### Copy configuration file

```bash
cp SmartMeter.excample.json SmartMeter.json
```

### Configuration

#### SmartMeter.json

スマートメーター にアクセスするための「B ルート認証情報」と、利用状況確認のために使う「契約アンペア数」、月間利用状況確認のために使う「検針日」を設定します。また、Ambient にデータを送信するのであれば、Ambient でチャンネル ID を作成し、ライトキーと合わせて設定してください。

| Name              | Description               | Example                                                 |
| ----------------- | ------------------------- | ------------------------------------------------------- |
| id                | B ルート認証 ID           | "000000XXXXXX00000000000000XXXXXX"                      |
| password          | B ルート認証 I パスワード | "XXXXXXXXXXXX"                                          |
| contract_amperage | 契約アンペア数            | "50"                                                    |
| charge_func       | 電気料金計算関数名        | "tokyo_gas_1"                                           |
| collect_date      | 検針日                    | "22"                                                    |
| ambient           | Ambient のチャンネル情報  | {"channel_id": "XXXXX","write_key": "XXXXXXXXXXXXXXXX"} |

#### 電気料金計算

契約アンペアと検針日の情報があれば、おおよその電気料金を計算することができるので、charge.py で料金計算関数を定義できるようにしてあります。東京ガスの料金計算を実装してありますので、必要に応じて追加し、その関数名を SmartMeter.json の charge_func で指定してください（例: "charge_func": "tokyo_gas_1"）。関数の実装例は下記です。正確には各種割引とかあるのですが、変化量がわかればいいので、正確な実装ではありません。

```python
def tokyo_gas_1(contract, power):
    """
    TOKYO GAS「ずっとも電気1」での電気料金計算

    Parameters
    ----------
    contract : str
        契約アンペア数
    power : float
        前回検針後の使用電力量（kWh）

    Returns
    -------
    fee: int
        電気料金
    """
    fee = {'30': 858.00, '40': 1144.00, '50': 1430.00, '60': 1716.00}[contract]

    if power <= 140:
        fee += 23.67 * power
    elif power <= 350:
        fee += 23.67 * 140
        fee += 23.88 * (power - 140)
    else:
        fee += 23.67 * 140
        fee += 23.88 * 350
        fee += 26.41 * (power - 140 - 350)
    return int(fee)
```

#### Ambient

SmartMeter.json で Ambient のチャンネル情報を設定すると、30 秒に一度（1 日に 2,880 回 < Ambient の上限値 3,000）データを送信します。送信するデータと単位は以下の通りです。

| Name       | Unit | Description                              |
| ---------- | ---- | ---------------------------------------- |
| データー 1 | A    | 瞬時電流計測値(E8)                       |
| データー 2 | kW   | 瞬時電力計測値(E7)                       |
| データー 3 | kWh  | 当月（前回検針後）の積算電力量計測値(EA) |
| データー 4 | 円   | 当月（前回検針後）の電気料金             |

## Install

必要なファイルを M5StackC にコピーします。

/flash/apps/

- SMM.py

/flash/

- BP35A1.py
- ambient.py
- charge.py
- ntpdate.py
- SmartMeter.json

## Debug

ログレベル DEBUG でログが出力されています。M5StickC のシリアルに接続して、動作状況を確認してください。

```bash
screen /dev/tty.usbserial-00001214 115200
```

## Credit

- [M5StickC で家庭用スマートメーターをハックする！](https://kitto-yakudatsu.com/archives/7206)

- [B ルートやってみた - スカイリー・ネットワークス](http://www.skyley.com/products/b-route.html)

- [特定省電力無線モジュール BP35A1 スタートガイド](https://micro.rohm.com/jp/download_support/wi-sun/data/other/bp35a1-startguide_v150.pdf)

- [BP35A1 コマンドリファレンスマニュアル（SE 版）](https://rabbit-note.com/wp-content/uploads/2016/12/50f67559796399098e50cba8fdbe6d0a.pdf)

- [ECHONET 規格書 Version 3.21 （日本語版）/ APPENDIX ECHONET 機器オブジェクト詳細規定](https://echonet.jp/spec_g/#standard-02)
