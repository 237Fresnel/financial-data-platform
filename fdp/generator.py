import argparse
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

COUNTRIES = ["FR", "DE", "ES", "IT", "BE", "GB", "US"]
COUNTRY_PROBS = [0.5, 0.1, 0.1, 0.1, 0.1, 0.05, 0.05]
CURRENCIES = {"FR": "EUR", "DE": "EUR", "ES": "EUR", "IT": "EUR",
              "BE": "EUR", "GB": "GBP", "US": "USD"}
TX_TYPES = ["card_payment", "transfer", "withdrawal", "direct_debit"]
TX_TYPE_PROBS = [0.6, 0.2, 0.1, 0.1]
_w = np.array([1, 1, 1, 1, 1, 2, 4, 6, 8, 8, 8, 8, 9, 8, 8, 8, 8, 8, 8, 7, 6, 4, 3, 2], float)
HOUR_PROBS = _w / _w.sum()  # activité surtout en journée

DEFECT_TYPES = ["missing_id", "non_positive_amount", "unknown_currency",
                "unknown_account", "invalid_timestamp"]

FRAUD_SCENARIOS = ["amount_spike", "foreign_country", "night_activity", "burst"]


def generate_reference(n_customers: int, seed: int):
    rng = np.random.default_rng(seed)
    ids = [f"C{i:06d}" for i in range(n_customers)]
    customers = pd.DataFrame({
        "customer_id": ids,
        "country": rng.choice(COUNTRIES, n_customers, p=COUNTRY_PROBS),
        "segment": rng.choice(["retail", "business"], n_customers, p=[0.9, 0.1]),
        "created_at": pd.Timestamp("2020-01-01")
                      + pd.to_timedelta(rng.integers(0, 1800, n_customers), unit="D"),
        # profil caché : sert au générateur, jamais exporté
        "typical_amount": rng.lognormal(3.5, 0.6, n_customers).round(2),
    })
    owners = np.repeat(ids, rng.integers(1, 3, n_customers))  # 1 à 2 comptes
    accounts = pd.DataFrame({
        "account_id": [f"A{i:07d}" for i in range(len(owners))],
        "customer_id": owners,
    }).merge(customers[["customer_id", "country", "created_at"]], on="customer_id")
    accounts["currency"] = accounts["country"].map(CURRENCIES)
    accounts["status"] = "active"
    return customers, accounts[["account_id", "customer_id", "currency", "status", "created_at"]]


def generate_day(day: date, customers, accounts, n_tx: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng([seed, day.toordinal()])  # un flux aléatoire par jour
    acc = accounts.merge(customers[["customer_id", "country", "typical_amount"]], on="customer_id")
    picked = acc.iloc[rng.integers(0, len(acc), n_tx)].reset_index(drop=True)

    seconds = rng.choice(24, n_tx, p=HOUR_PROBS) * 3600 + rng.integers(0, 3600, n_tx)
    abroad = rng.random(n_tx) < 0.03
    df = pd.DataFrame({
        "transaction_id": [f"T{day:%Y%m%d}{i:06d}" for i in range(n_tx)],
        "account_id": picked["account_id"],
        "counterparty_account_id": [f"X{v:07d}" for v in rng.integers(0, 10**7, n_tx)],
        "amount": (picked["typical_amount"] * rng.lognormal(0, 0.4, n_tx)).round(2).clip(lower=0.01),
        "currency": picked["currency"],
        "transaction_type": rng.choice(TX_TYPES, n_tx, p=TX_TYPE_PROBS),
        "country": np.where(abroad, rng.choice(COUNTRIES, n_tx), picked["country"]),
        "transaction_timestamp": pd.Timestamp(day) + pd.to_timedelta(seconds, unit="s"),  # UTC
    })
    return df.sort_values("transaction_timestamp").reset_index(drop=True)


def inject_defects(df, rng, rate=0.01, duplicate_rate=0.01, exclude_ids=()):
    ...
    """Retourne (données dégradées, manifeste des défauts injectés)."""
    df = df.copy()
    df["transaction_timestamp"] = df["transaction_timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    n_each = int(len(df) * rate)
    candidates = np.flatnonzero(~df["transaction_id"].isin(exclude_ids))   # nouveau
    chosen = rng.choice(candidates, n_each * len(DEFECT_TYPES), replace=False)  # len(df) → candidates
    manifest = []

    for k, defect in enumerate(DEFECT_TYPES):
        rows = chosen[k * n_each:(k + 1) * n_each]
        manifest += [(tid, defect) for tid in df.loc[rows, "transaction_id"]]
        if defect == "missing_id":
            df.loc[rows, "transaction_id"] = ""
        elif defect == "non_positive_amount":
            df.loc[rows, "amount"] = -df.loc[rows, "amount"]
        elif defect == "unknown_currency":
            df.loc[rows, "currency"] = "ZZZ"
        elif defect == "unknown_account":
            df.loc[rows, "account_id"] = "A9999999"
        elif defect == "invalid_timestamp":
            df.loc[rows, "transaction_timestamp"] = "2026-13-45 25:61:00"

    clean = np.setdiff1d(candidates, chosen)
    dups = df.loc[rng.choice(clean, int(len(df) * duplicate_rate), replace=False)]
    manifest += [(tid, "duplicate") for tid in dups["transaction_id"]]
    df = pd.concat([df, dups])
    df = df.iloc[rng.permutation(len(df))].reset_index(drop=True)  # fichier non trié, réaliste
    return df, pd.DataFrame(manifest, columns=["transaction_id", "defect_type"])


def inject_frauds(df, customers, accounts, day, rng, rate=0.002):
    """Retourne (transactions avec fraudes, labels de vérité terrain)."""
    df = df.copy()
    profile = accounts.merge(customers[["customer_id", "country", "typical_amount"]],
                             on="customer_id").set_index("account_id")
    n = max(1, int(len(df) * rate))
    spike, foreign, night = np.split(rng.choice(len(df), 3 * n, replace=False), 3)
    labels = []

    # 1. Montant anormal
    typical = profile.loc[df.loc[spike, "account_id"], "typical_amount"].to_numpy()
    df.loc[spike, "amount"] = (typical * rng.uniform(8, 20, n)).round(2)

    # 2. Pays différent du pays de résidence
    home = profile.loc[df.loc[foreign, "account_id"], "country"].to_numpy()
    df.loc[foreign, "country"] = [rng.choice([c for c in COUNTRIES if c != h]) for h in home]

    # 3. Activité nocturne avec montant élevé
    secs = rng.integers(3600, 5 * 3600, n)
    df.loc[night, "transaction_timestamp"] = pd.Timestamp(day) + pd.to_timedelta(secs, unit="s")
    df.loc[night, "amount"] = (df.loc[night, "amount"] * 3).round(2)

    for name, rows in [("amount_spike", spike), ("foreign_country", foreign),
                       ("night_activity", night)]:
        labels += [(tid, name) for tid in df.loc[rows, "transaction_id"]]

    # 4. Rafale : nouvelles transactions, montants normaux, seule la fréquence est suspecte
    bursts = []
    for b in range(n):
        acc_id = rng.choice(profile.index)
        start = pd.Timestamp(day) + pd.Timedelta(seconds=int(rng.integers(0, 86400 - 600)))
        for k in range(int(rng.integers(5, 9))):
            tid = f"T{day:%Y%m%d}B{b:03d}{k:02d}"
            bursts.append({
                "transaction_id": tid,
                "account_id": acc_id,
                "counterparty_account_id": f"X{int(rng.integers(0, 10**7)):07d}",
                "amount": round(profile.at[acc_id, "typical_amount"] * rng.uniform(0.5, 1.5), 2),
                "currency": profile.at[acc_id, "currency"],
                "transaction_type": "card_payment",
                "country": profile.at[acc_id, "country"],
                "transaction_timestamp": start + pd.Timedelta(seconds=int(rng.integers(0, 600))),
            })
            labels.append((tid, "burst"))

    df = (pd.concat([df, pd.DataFrame(bursts)])
            .sort_values("transaction_timestamp").reset_index(drop=True))
    return df, pd.DataFrame(labels, columns=["transaction_id", "scenario"])

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--start", type=date.fromisoformat, required=True)
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--customers", type=int, default=1000)
    p.add_argument("--tx-per-day", type=int, default=2000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", type=Path, default=Path("data/landing"))
    p.add_argument("--truth-out", type=Path, default=Path("data/ground_truth"))
    args = p.parse_args()
    args.truth_out.mkdir(parents=True, exist_ok=True)

    customers, accounts = generate_reference(args.customers, args.seed)
    ref = args.out / "reference"
    ref.mkdir(parents=True, exist_ok=True)
    customers.drop(columns="typical_amount").to_csv(ref / "customers.csv", index=False)
    accounts.to_csv(ref / "accounts.csv", index=False)

    for i in range(args.days):
        day = args.start + timedelta(days=i)
        tx = generate_day(day, customers, accounts, args.tx_per_day, args.seed)
        rng_fraud = np.random.default_rng([args.seed, day.toordinal(), 2])
        tx, frauds = inject_frauds(tx, customers, accounts, day, rng_fraud)
        rng_defects = np.random.default_rng([args.seed, day.toordinal(), 1])
        dirty, manifest = inject_defects(tx, rng_defects, exclude_ids=frauds["transaction_id"])
        dirty.to_csv(args.out / f"transactions_{day:%Y-%m-%d}.csv", index=False)
        manifest.to_csv(args.truth_out / f"defects_{day:%Y-%m-%d}.csv", index=False)
        frauds.to_csv(args.truth_out / f"frauds_{day:%Y-%m-%d}.csv", index=False)
if __name__ == "__main__":
    main()