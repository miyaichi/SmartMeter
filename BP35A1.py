import logging
import machine
import utime
from m5stack import lcd

# global variables

logger = None

# decoretor


def iofunc(func):
    def wrapper(obj, *args):
        if (args):
            logger.debug('> %s', args[0].strip())
        response = func(obj, *args)
        if (response):
            logger.debug('< %s', response.decode().strip())
        utime.sleep(0.5)
        return response

    return wrapper


def skfunc(func):
    def wrapper(obj, *args, **kwds):
        logger.debug('%s', func.__name__)
        utime.sleep(0.5)
        response = func(obj, *args, **kwds)
        if response:
            logger.info('%s: Succeed', func.__name__)
        else:
            logger.error('%s: Failed', func.__name__)
        utime.sleep(0.5)
        return response

    return wrapper


def propfunc(func):
    def wrapper(obj, *args, **kwds):
        logger.info('%s: %s', func.__name__, args)
        response = func(obj, *args, **kwds)
        logger.info('%s: %s', func.__name__, response)
        utime.sleep(0.5)
        return response

    return wrapper


# date time function


def day_of_week(y, m, d):
    t = (0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4)
    if m < 3:
        y -= 1
    return (y + y // 4 - y // 100 + y // 400 + t[m - 1] + d) % 7


def days_of_year(y, m, d):
    t = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    if m > 2 and (y % 4 == 0) and (y % 100 == 0 or y % 400 != 0):
        d += 1
    return sum(t[:m - 1]) + d


def localtime():
    offset = 9 * 3600  # JST
    return utime.localtime(utime.mktime(utime.localtime()) + offset)


def strftime(tm, *, fmt='{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}'):
    (year, month, mday, hour, minute, second) = tm[:6]
    return fmt.format(year, month, mday, hour, minute, second)


def days_after_collect(collect_mday):
    (year, month, mday) = localtime()[:3]
    if month == 1:
        return 31 - collect_mday + mday
    days1 = days_of_year(year, month, mday)
    if mday < collect_mday:
        month -= 1
    days2 = days_of_year(year, month, collect_mday)
    return days1 - days2


def last_colect_day(collect_mday):
    (year, month, mday) = localtime()[:3]
    if month == 1:
        return (year - 1, 12, 31 - collect_mday + mday)
    if mday < collect_mday:
        month -= 1
    return strftime((year, month, collect_mday, 0, 0, 0))


class BP35A1:
    def __init__(self,
                 id,
                 password,
                 contract_amperage,
                 collect_date,
                 *,
                 progress_func=None,
                 logger_name=__name__):
        global logger
        logger = logging.getLogger(logger_name)
        self.progress = progress_func if progress_func else lambda _: None

        self.uart = machine.UART(1, tx=0, rx=36)
        self.uart.init(115200, bits=8, parity=None, stop=1, timeout=2000)

        self.id = id
        self.password = password
        self.contract_amperage = int(contract_amperage)
        self.collect_date = int(collect_date)

        self.channel = None
        self.pan_id = None
        self.mac_addr = None
        self.lqi = None

        self.ipv6_addr = None
        self.power_coefficient = None
        self.power_unit = None

        self.timeout = 60

    def flash(self):
        utime.sleep(0.5)
        while self.uart.any():
            _ = self.uart.read()
        self.uart.write('\r\n')
        utime.sleep(0.5)

    def need_scan(self):
        return not (self.channel and self.pan_id and self.mac_addr
                    and self.lqi)

    def reset_scan(self):
        self.channel = self.pan_id = self.mac_addr = self.lqi = None

    @iofunc
    def readln(self):
        s = utime.time()
        while utime.time() - s < self.timeout:
            if self.uart.any():
                return self.uart.readline()
        raise Exception('BP35A1.readln() timeout.')

    @iofunc
    def write(self, data):
        self.uart.write(data)

    @iofunc
    def writeln(self, data):
        self.uart.write(data + '\r\n')

    def exec_command(self, cmd, arg=''):
        self.writeln(cmd + arg)
        return self.wait_for_ok()

    @skfunc
    def skInit(self):
        return self.exec_command('SKRESET') and self.exec_command(
            'SKSREG SFE 0') and self.exec_command(
                'ROPT') and self.exec_command('WOPT 01')

    @skfunc
    def skVer(self):
        return self.exec_command('SKVER')

    @skfunc
    def skSetPasswd(self):
        return self.exec_command('SKSETPWD C ', self.password)

    @skfunc
    def skSetID(self):
        return self.exec_command('SKSETRBID ', self.id)

    @skfunc
    def skSetChannel(self):
        return self.exec_command('SKSREG S2 ', self.channel)

    @skfunc
    def skSetPanID(self):
        return self.exec_command('SKSREG S3 ', self.pan_id)

    @skfunc
    def skTerm(self):
        return self.exec_command('SKTERM')

    @skfunc
    def skScan(self, duration=6):
        while duration <= 10:
            self.reset_scan()
            self.writeln('SKSCAN 2 FFFFFFFF ' + str(duration))
            while True:
                ln = self.readln()
                if ln.startswith('EVENT 22'):
                    break

                if ':' in ln:
                    key, val = ln.decode().strip().split(':')[:2]
                    if key == 'Channel':
                        self.channel = val
                    elif key == 'Pan ID':
                        self.pan_id = val
                    elif key == 'Addr':
                        self.mac_addr = val
                    elif key == 'LQI':
                        self.lqi = val

            if self.channel and self.pan_id and self.mac_addr and self.lqi:
                return True

            duration = duration + 1

        return False

    @skfunc
    def skLL64(self):
        self.writeln('SKLL64 ' + self.mac_addr)
        while True:
            ln = self.readln()
            val = ln.decode().strip()
            if val:
                self.ipv6_addr = val
                return True

    @skfunc
    def skPing(self):
        self.writeln('SKPING ' + self.ipv6_addr)
        while True:
            ln = self.readln()
            val = ln.decode().strip()
            if val.startswith('EPONG'):
                return True

    @skfunc
    def skJoin(self):
        self.writeln('SKJOIN ' + self.ipv6_addr)
        while True:
            ln = self.readln()
            if ln.startswith('EVENT 24'):
                return False
            elif ln.startswith('EVENT 25'):
                return True

    @skfunc
    def skSendTo(self, data):
        self.write('SKSENDTO 1 {0} 0E1A 1 {1:04X} '.format(
            self.ipv6_addr, len(data)))
        self.write(data)
        return True

    @propfunc
    def read_propaty(self, epc):
        """
        プロパティ値読み出し
        """
        self.skSendTo((
            b'\x10\x81'  # EHD
            b'\x00\x01'  # TID
            b'\x05\xFF\x01'  # SEOJ
            b'\x02\x88\x01'  # DEOJ 低圧スマート電力量メータークラス
            b'\x62'  # ESV プロパティ値読み出し(62)
            b'\x01'  # OPC 1個
        ) + bytes([int(epc, 16)]) + (
            b'\x00'  # PDC Read
        ))
        return self.wait_for_data()

    @propfunc
    def write_property(self, epc, value):
        """
        プロパティ値書き込み
        """
        self.skSendTo((
            b'\x10\x81'  # EHD
            b'\x00\x01'  # TID
            b'\x05\xFF\x01'  # SEOJ
            b'\x02\x88\x01'  # DEOJ 低圧スマート電力量メータークラス
            b'\x61'  # ESV プロパティ値書き込み(61)
            b'\x01'  # OPC 1個
        ) + bytes([int(epc, 16)]) + (
            b'\x01'  # PDC Write
        ) + bytes([value]))
        return self.wait_for_data()

    def open(self):
        """
        スマートメーターへの接奥
        """
        # バッファをクリア
        self.progress(0)
        self.flash()

        # BP53A1の初期化
        self.progress(10)
        if not self.skInit():
            return False

        # Bルート認証IDの設定
        self.progress(30)
        if not (self.skSetPasswd() and self.skSetID()):
            return False

        while True:
            try:
                # スマートメーターのスキャン
                self.progress(40)
                if self.need_scan():
                    if not self.skScan():
                        continue

                # IPV6アドレスの取得
                self.progress(50)
                if not self.skLL64():
                    continue

                # 無線CH設定、受信PAN-IDの設定
                self.progress(60)
                if not (self.skSetChannel() and self.skSetPanID()):
                    continue

                # スマートメーターに接続
                self.progress(70)
                if not self.skJoin():
                    # スキャン結果をリセット
                    self.reset_scan()
                    continue

                # 係数(D3)の取得
                self.progress(80)
                self.power_coefficient = self.read_propaty('D3')

                # 積算電力量単位(E1)の取得
                self.progress(90)
                self.power_unit = self.read_propaty('E1')

                self.progress(100)
                return (self.channel, self.pan_id, self.mac_addr, self.lqi)

            except Exception as e:
                logger.error(e)

    def total_power(self):
        """
        積算電力量計測値(EA)の取得
        """
        return self.read_propaty('EA')

    def instantaneous_power(self):
        """
        瞬時電力計測値(E7)の取得
        """
        return self.read_propaty('E7')

    def instantaneous_amperage(self):
        """
        瞬時電流計測値(E8)の取得
        """
        return self.read_propaty('E8')

    def monthly_power(self):
        """
        前回検針日を起点とした積算電力量計測値履歴１(E2)の取得
        """
        # 積算履歴収集日１(E5)の設定
        self.write_property('E5', days_after_collect(self.collect_date))

        # 積算電力量計測値履歴１(E2)の取得
        (days, collected_power) = self.read_propaty('E2')

        # 瞬時電力計測値(E7)の取得
        (created, power) = self.read_propaty('EA')

        # 前回検針日と積算電力量計測値(EA)との差分
        return (last_colect_day(self.collect_date), power - collected_power)

    def close(self):
        """
        スマートメーターとの接奥解除
        """
        self.skTerm()

    def wait_for_ok(self):
        while True:
            ln = self.readln()
            if ln.startswith('OK'):
                return True
            elif ln.startswith('FAIL'):
                return False

    def wait_for_data(self):
        start = utime.time()
        while utime.time() - start < self.timeout:
            ln = self.readln()
            if not ln.startswith('ERXUDP'):
                continue

            values = ln.decode().strip().split(' ')
            if not len(values) == 9:
                continue

            data = values[8]
            seoj = data[8:8 + 6]
            esv = data[20:20 + 2]
            epc = data[24:24 + 2]

            # 低圧スマート電力量メータ(028801)
            if seoj != '028801':
                continue

            # 積算電力量係数
            if esv == '72' and epc == 'D3':
                power_coefficient = int(data[-8:], 16)
                return power_coefficient

            # 積算電力量単位
            if esv == '72' and epc == 'E1':
                power_unit = {
                    '00': 1.0,
                    '01': 0.1,
                    '02': 0.01,
                    '03': 0.001,
                    '04': 0.0001,
                    '0A': 10.0,
                    '0B': 100.0,
                    '0C': 1000.0,
                    '0D': 10000.0,
                }[data[-2:]]
                return power_unit

            # 積算電力量計測値履歴１
            if esv == '72' and epc == 'E2':
                days = int(data[30:30 + 2], 16)
                power = int(data[32:32 + 8],
                            16) * self.power_coefficient * self.power_unit
                return days, power

            # 積算履歴収集日１
            if esv == '71' and epc == 'E5':
                result = int(data[-2:], 16)
                return result

            # 瞬時電力値
            if esv == '72' and epc == 'E7':
                power = int(data[-8:], 16)
                return strftime(localtime()), power

            # 瞬時電流計測値
            if esv == '72' and epc == 'E8':
                r = int(data[-8:-8 + 4], 16)
                if r == 0x7ffe:
                    r = 0
                t = int(data[-4:], 16)
                if t == 0x7ffe:
                    t = 0
                return strftime(localtime()), (r + t) / 10.0

            # 定時積算電力量
            if esv == '72' and epc == 'EA':
                (year, month, mday, hour, minute,
                 second) = (int(data[-22:-22 + 4],
                                16), int(data[-18:-18 + 2],
                                         16), int(data[-16:-16 + 2], 16),
                            int(data[-14:-14 + 2],
                                16), int(data[-12:-12 + 2],
                                         16), int(data[-10:-10 + 2], 16))
                created = strftime((year, month, mday, hour, minute, second))
                power = int(data[-8:],
                            16) * self.power_coefficient * self.power_unit
                return created, power

        raise Exception('BP35A1.wait_for_data() timeout.')

    def close(self):
        self.skTerm()


if __name__ == '__main__':
    id = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
    password = 'xxxxxxxxxxxx'
    contract_amperage = "50"
    collect_date = "22"

    bp35a1 = BP35A1(id, password, contract_amperage, collect_date)

    bp35a1.open()

    (datetime, data) = bp35a1.instantaneous_power()
    print('Instantaneous power {} {}W'.format(datetime, data))

    (datetime, data) = bp35a1.total_power()
    print('Total power {} {}kWh'.format(datetime, data))

    bp35a1.close()