from models import *
from preprocesor import *
import pandas as pd
from sklearn.preprocessing import StandardScaler


class Dataset:
    def __init__(self, raw, xtrain_mean=None, ytrain_mean=None,
                 xtest_mean=None, ytest_mean=None,
                 xtrain_ohlc=None, ytrain_ohlc=None,
                 xtest_ohlc=None, ytest_ohlc=None):
        self.raw = raw
        self.xtrain_mean = xtrain_mean
        self.ytrain_mean = ytrain_mean
        self.xtest_mean = xtest_mean
        self.ytest_mean = ytest_mean
        self.xtrain_ohlc = xtrain_ohlc
        self.ytrain_ohlc = ytrain_ohlc
        self.xtest_ohlc = xtest_ohlc
        self.ytest_ohlc = ytest_ohlc
        self.scaler = None


def load_dataset(path, scaler, resample='1D', lag=4):

    df = pd.read_csv(path, index_col=0)
    df.set_index(pd.to_datetime(df.index, unit='s'), inplace=True)
    df.sort_index(inplace=True)
    dataset = Dataset(df)

    p1 = PreprocessDifferenciate(periods=1)
    p2 = PreprocessScikitScaler(scaler)
    p3 = PreprocessLagMatrix(lag)
    p4 = PreprocessRemoveFirstElements(lag)
    preprocessList = PreprocessList([p1, p2, p3, p4])

    ohlc = df['Price'].resample(resample).ohlc().fillna(method='ffill')
    x, y = preprocessList.execute(ohlc)
    x_train, y_train, x_test, y_test = test_train_split_timestamp(x, y)

    dataset.xtrain_ohlc, dataset.ytrain_ohlc = x_train, y_train
    dataset.xtest_ohlc, dataset.ytest_ohlc = x_test, y_test

    mean = df['Price'].resample(resample).mean().fillna(method='ffill')
    x, y = preprocessList.execute(mean)
    x_train, y_train, x_test, y_test = test_train_split_timestamp(x, y)

    dataset.xtrain_mean, dataset.ytrain_mean = x_train, y_train
    dataset.xtest_mean, dataset.ytest_mean = x_test, y_test

    return dataset


def train_model(x, y, test_data, n_inputs, n_outputs):
    model = simple_model(n_inputs, n_outputs)
    best = BestModelCallback()
    model.fit(x, y, epochs=200, validation_data=test_data, shuffle=False,
              verbose=2)

    return model


if __name__ == '__main__':
    import matplotlib.pyplot as plt
    from sklearn.preprocessing import StandardScaler

    scaler = StandardScaler()
    dataset = load_dataset('bitcoin.csv', scaler=scaler, resample='1D', lag=3)
    x = dataset.xtrain_mean
    y = dataset.ytrain_mean
    xt = dataset.xtest_mean
    yt = dataset.ytest_mean

    model = train_model(x.values, y.values, (xt.values, yt.values), 1, 1)
    ypred = model.predict(xt)

    plt.plot(yt.values, label='ytrue')
    plt.plot(ypred, label='ypred')
    plt.legend()
    plt.savefig('im.png', dpi=300)
