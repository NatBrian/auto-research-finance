import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from src.execution_model import apply_costs
from src.metrics import annualized_return, sharpe_ratio

try:
    from xgboost import XGBClassifier
except Exception:  # pragma: no cover - dependency may be absent in thin envs
    XGBClassifier = None


class MLBaseline:
    def __init__(self, train_data: pd.DataFrame, test_data: pd.DataFrame):
        self.train_data = train_data.sort_index()
        self.test_data = test_data.sort_index()

    @staticmethod
    def _build_features(data: pd.DataFrame) -> pd.DataFrame:
        close = data["Close"].astype(float)
        volume = data["Volume"].astype(float)

        close_lag1 = close.groupby(level="ticker").shift(1)
        close_lag5 = close.groupby(level="ticker").shift(6)
        close_lag20 = close.groupby(level="ticker").shift(21)

        feat_5d = np.log(close_lag1 / close_lag5)
        feat_20d = np.log(close_lag1 / close_lag20)

        vol_lag1 = volume.groupby(level="ticker").shift(1)
        vol_mean5 = vol_lag1.groupby(level="ticker").transform(lambda x: x.rolling(5).mean())
        vol_std5 = vol_lag1.groupby(level="ticker").transform(lambda x: x.rolling(5).std())
        vol_z = (vol_lag1 - vol_mean5) / vol_std5.replace(0.0, np.nan)

        log_ret_1d = np.log(close / close.groupby(level="ticker").shift(1))
        vol_20 = log_ret_1d.groupby(level="ticker").transform(lambda x: x.rolling(20).std())
        vol_20 = vol_20.groupby(level="ticker").shift(1)

        return pd.DataFrame(
            {
                "ret_5d": feat_5d,
                "ret_20d": feat_20d,
                "vol_z_5d": vol_z,
                "volatility_20d": vol_20,
            }
        )

    @staticmethod
    def _forward_5d_returns(data: pd.DataFrame) -> pd.Series:
        close = data["Close"].astype(float)
        fwd = close.groupby(level="ticker").shift(-5) / close - 1.0
        return fwd

    @staticmethod
    def _annualized_return(returns: pd.Series) -> float:
        return annualized_return(returns)

    def run(self) -> dict:
        result = {
            "xgb_sharpe": np.nan,
            "logreg_sharpe": np.nan,
            "xgb_annual_return": np.nan,
            "logreg_annual_return": np.nan,
        }

        train_features = self._build_features(self.train_data)
        test_features = self._build_features(self.test_data)

        train_fwd = self._forward_5d_returns(self.train_data)
        test_fwd = self._forward_5d_returns(self.test_data)

        valid_train_target = train_fwd.dropna()
        if valid_train_target.empty:
            return result

        quantiles = valid_train_target.quantile([0.2, 0.4, 0.6, 0.8]).values
        bins = [-np.inf, *quantiles.tolist(), np.inf]
        labels = [1, 2, 3, 4, 5]

        train_target = pd.cut(train_fwd, bins=bins, labels=labels).astype(float)
        test_target = pd.cut(test_fwd, bins=bins, labels=labels).astype(float)

        train_ds = train_features.copy()
        train_ds["target"] = train_target
        train_ds = train_ds.dropna()

        test_ds = test_features.copy()
        test_ds["target"] = test_target
        test_ds = test_ds.dropna()

        if train_ds.empty or test_ds.empty:
            return result

        x_train = train_ds.drop(columns=["target"])
        y_train = train_ds["target"].astype(int)
        x_test = test_ds.drop(columns=["target"])

        scaler = StandardScaler()
        x_train_scaled = scaler.fit_transform(x_train)
        x_test_scaled = scaler.transform(x_test)

        if XGBClassifier is not None:
            try:
                xgb = XGBClassifier(
                    n_estimators=100,
                    max_depth=3,
                    random_state=42,
                    use_label_encoder=False,
                    eval_metric="mlogloss",
                )
                xgb.fit(x_train_scaled, y_train)
                xgb_proba = xgb.predict_proba(x_test_scaled)
                class_to_idx = {c: i for i, c in enumerate(xgb.classes_)}
                top_class_idx = class_to_idx.get(5, len(xgb.classes_) - 1)
                xgb_signal = pd.Series(xgb_proba[:, top_class_idx], index=x_test.index)

                xgb_returns = apply_costs(xgb_signal, self.test_data, cost_bps=10)
                result["xgb_sharpe"] = sharpe_ratio(xgb_returns)
                result["xgb_annual_return"] = self._annualized_return(xgb_returns)
            except Exception:
                pass

        try:
            logreg = LogisticRegression(max_iter=1000, random_state=42)
            logreg.fit(x_train_scaled, y_train)
            lr_proba = logreg.predict_proba(x_test_scaled)
            class_to_idx = {c: i for i, c in enumerate(logreg.classes_)}
            top_class_idx = class_to_idx.get(5, len(logreg.classes_) - 1)
            lr_signal = pd.Series(lr_proba[:, top_class_idx], index=x_test.index)

            lr_returns = apply_costs(lr_signal, self.test_data, cost_bps=10)
            result["logreg_sharpe"] = sharpe_ratio(lr_returns)
            result["logreg_annual_return"] = self._annualized_return(lr_returns)
        except Exception:
            pass

        return result
