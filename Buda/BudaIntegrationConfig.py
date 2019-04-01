import pandas as pd

from core.config import BaseConfig, MarketConfig


class MarketsId:
    btc = 'btc-clp'
    eth = 'eth-clp'
    ltc = 'ltc-clp'
    bch = 'bch-clp'


class BudaMarketConfig(BaseConfig):
    sleep_time_sec: int = 10  # time intervals betweern calls. Increase to prevent being blocked by ddos policies
    sleep_time_after_block: int = 60 * 5  # 5 min
    # the string must match the pandas offset aliases
    # http://pandas.pydata.org/pandas-docs/stable/user_guide/timeseries.html#offset-aliases
    resample_interval: str = '1H'
    base_url = 'https://www.buda.com/api/v2/markets/'

    btc: MarketConfig = None
    eth: MarketConfig = None
    ltc: MarketConfig = None
    bch: MarketConfig = None
    root_config = None

    @classmethod
    def get_instanciator(cls):
        return BudaMarketConfig()

    @classmethod
    def get_market_config_instance(cls, **kwargs):
        return MarketConfig(**kwargs)

    # def persist(self, path='budaConfig.json'):
    #     json_dict = {
    #         'sleep_time_sec': self.sleep_time_sec,
    #         'sleep_time_after_block': self.sleep_time_after_block,
    #         'resample_interval': self.resample_interval
    #     }
    #
    #     if self.btc is not None:
    #         json_dict['btc'] = self.btc.to_dict()
    #     if self.eth is not None:
    #         json_dict['eth'] = self.eth.to_dict()
    #     if self.ltc is not None:
    #         json_dict['ltc'] = self.ltc.to_dict()
    #     if self.bch is not None:
    #         json_dict['bch'] = self.bch.to_dict()
    #
    #     json_str = json.dumps(json_dict, indent=4)
    #
    #     with open(path, mode='w', encoding='UTF-8') as file:
    #         file.write(json_str)

    def is_valid(self):
        return self.btc is not None or \
               self.bch is not None or \
               self.ltc is not None or \
               self.eth is not None

    def __dir__(self):
        return ['sleep_time_sec', 'sleep_time_after_block', 'resample_interval', 'btc', 'eth', 'ltc', 'bch']


class BudaMarketTradeEntry:
    _TIMESAMP_INDEX = 0
    _AMOUNT_INDEX = 1
    _PRICE_INDEX = 2
    _DIRECTION_INDEX = 3

    def __init__(self, entry: list):
        self.timestamp = int(entry[self._TIMESAMP_INDEX])
        self.amount = float(entry[self._AMOUNT_INDEX])
        self.price = float(entry[self._PRICE_INDEX])
        # direction means if it is a buy or sell operation
        self.direction = entry[self._DIRECTION_INDEX]

    def to_dict(self):
        return {
            'timestamp': self.timestamp,
            'amount': self.amount,
            'price': self.price
        }

    def __eq__(self, other):
        if isinstance(other, BudaMarketTradeEntry):
            return other.__dict__ == self.__dict__
        else:
            return False

    def __str__(self):
        return self.__dict__


# Small abstraction class to avoid interact directly with the list of trades.
# The idea is to use the utility functions for better readibility,
# using the functions in specific order depending what it is intending to achieve.
#
# ============ Append all entries before converting to ohlc ===============
# trade_list = BudaMarketTradeList()
# while there are more entries:
#   trade_list.append_raw (tick_list)
#
# trade_list.resample_ohlcv()

# =========== resampling with every new entries_list ==============
# ====== useful to persist the data after each request =======
#
# trade_list = BudaMarketTradeList()
# entry_list = request_entries ()
# trade_list.append_and_resample(entry_list)
#
# while there are more entries:
#   entry_list = request_entries()
#   trade_list_ext = BudaMarketTradeList()
#
#   trade_list_ext.append_and_resample(entry_list)
#   trade_list.merge(trade_list_ext)
#
class BudaMarketTradeList:
    def __init__(self, existing_entries=None, filter_timestamp: int = None):
        self.trade_list = []
        self.filter_timestamp = filter_timestamp

        if existing_entries is not None:
            if isinstance(existing_entries, (list, pd.DataFrame)):
                self.trade_list = existing_entries
            else:
                raise AssertionError("The existing values must be a list or Dataframe type")

    def append_raw(self, new_entries: list):
        if self.is_resampled():
            raise AssertionError("Assertion Error: this instance must not be resampled to be able to append raw data.")

        for entry in new_entries:
            self.trade_list.append(BudaMarketTradeEntry(entry))

        return self.trade_list

    def resample_ohlcv(self):
        self.trade_list = pd.DataFrame([entry.to_dict() for entry in self.trade_list]).set_index('timestamp')
        # parses the index from timestamp in seconds to a format understandable for pandas
        self.trade_list.set_index(self.trade_list.index.values.astype('M8[ms]'), inplace=True)
        # self.trade_list.set_index(pd.to_datetime(self.trade_list.index, unit='ms').
        #                           tz_localize('Etc/GMT-4'),
        #                           inplace=True)

        self._filter_by_timestamp()

        ohlcv = self.trade_list['price'].resample('1H').ohlc().fillna(method='ffill')
        ohlcv['volume'] = self.trade_list['amount'].resample('1H').sum()

        ohlcv.index.name = 'date'
        self.trade_list = ohlcv
        return self.trade_list

    def append_and_resample(self, new_entries: list):
        self.append_raw(new_entries)
        self.resample_ohlcv()
        return self.trade_list

    def merge(self, trade_list):
        if not isinstance(trade_list, BudaMarketTradeList):
            raise TypeError('tradelist must be BudaMarketTradeList instance')
        elif not trade_list.is_resampled():
            raise ValueError('tradelist must be resampled to ohlc data before merge')
        elif not self.is_resampled():
            self.resample_ohlcv()

        merged: pd.DataFrame = self.trade_list.append(trade_list.trade_list)
        self.trade_list = merged.resample('1H').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).fillna(method='ffill')
        return self.trade_list

    def _filter_by_timestamp(self):
        if self.filter_timestamp is not None and isinstance(self.trade_list, pd.DataFrame):
            self.trade_list = self.trade_list[self.trade_list.timestamp > self.filter_timestamp]

    def is_resampled(self):
        return isinstance(self.trade_list, pd.DataFrame)
