# TOKYO GASの料金計算
# https://home.tokyo-gas.co.jp/power/ryokin/tanka/index.html


def tokyo_gas_1s(contract, power):
    """
    TOKYO GAS「ずっとも電気1S」での電気料金計算

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
    fee = {
        '10': 286.00,
        '15': 429.00,
        '20': 572.00,
        '40': 1144.00,
        '50': 1430.00,
        '60': 1716.0
    }[contract]

    if power <= 120:
        fee += 19.85 * power
    elif power <= 300:
        fee += 19.85 * 120
        fee += 25.35 * (power - 120)
    else:
        fee += 19.85 * 120
        fee += 25.35 * 300
        fee += 27.48 * (power - 120 - 300)
    return int(fee)


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


def tokyo_gas_2(contract, power):
    """
    TOKYO GAS「ずっとも電気2」での電気料金計算

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
    fee = 286.00
    if power <= 360:
        fee += 19.85 * power
    else:
        fee += 23.63 * 360
        fee += 26.47 * (power - 360)
    return int(fee)


if __name__ == '__main__':
    print(tokyo_gas_1('50', 339))
