"""從臺灣證券交易所 OpenAPI 下載上市公司月營收與綜合損益表,輸出 data/fundamentals.json。
僅使用 Python 標準函式庫。資料來源:https://openapi.twse.com.tw
"""
import json, sys, time, urllib.request, datetime, pathlib

BASE = "https://openapi.twse.com.tw/v1/opendata/"
OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "fundamentals.json"


def get(name, tries=4):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(BASE + name, headers={"User-Agent": "Mozilla/5.0 stock-health-check", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8-sig"))
        except Exception as e:  # noqa
            last = e
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"下載失敗 {name}: {last}")


def f(x):
    try:
        return float(str(x).replace(",", ""))
    except Exception:
        return None


def pct(x):
    v = f(x)
    return None if v is None else v / 100.0


def main():
    stocks = {}
    prev = {}
    if OUT.exists():
        try:
            prev = json.loads(OUT.read_text(encoding="utf-8")).get("stocks", {})
        except Exception:
            prev = {}
    for r in get("t187ap05_L"):
        code = r.get("公司代號")
        if not code:
            continue
        ym = str(r.get("資料年月", ""))
        month = f"{ym[:-2]}/{ym[-2:]}" if len(ym) >= 4 else ym
        stocks[code] = {
            "name": r.get("公司名稱"), "industry": r.get("產業別"), "month": month,
            "rev": f(r.get("營業收入-當月營收")), "rev_mom": pct(r.get("營業收入-上月比較增減(%)")),
            "rev_yoy": pct(r.get("營業收入-去年同月增減(%)")), "ytd_yoy": pct(r.get("累計營業收入-前期比較增減(%)")),
        }
        # 逐月累積歷史月營收(億元),保留最近 24 個月
        hist = dict(prev.get(code, {}).get("hist", {}))
        rv = f(r.get("營業收入-當月營收"))
        if month and rv is not None:
            hist[month] = round(rv / 1e5, 2)
        stocks[code]["hist"] = dict(sorted(hist.items())[-24:])
    eps = {}
    for r in get("t187ap14_L"):
        code = r.get("公司代號")
        if code:
            eps[code] = {"year": r.get("年度"), "season": r.get("季別"), "eps": f(r.get("基本每股盈餘(元)"))}
    margins = {}
    try:
        for r in get("t187ap06_L_ci"):
            code = r.get("公司代號") or ""
            rev = f(r.get("營業收入"))
            if code and rev:
                gp, op, ni = (f(r.get(k)) for k in ("營業毛利", "營業利益", "本期淨利"))
                if gp is None and f(r.get("營業成本")) is not None:
                    gp = rev - f(r.get("營業成本"))
                if gp is not None and op is not None and ni is not None:
                    margins[code] = {"gm": gp / rev, "om": op / rev, "nm": ni / rev}
    except Exception as e:  # 毛利率為加分資料,失敗不中斷
        print("警告:無法取得綜合損益表(一般業):", e, file=sys.stderr)
    for code, e in eps.items():
        s = stocks.setdefault(code, {"name": None, "industry": None})
        q = dict(e)
        q.update(margins.get(code, {}))
        s["q"] = q
    if len(stocks) < 500:
        raise SystemExit(f"資料筆數異常偏少({len(stocks)}),不覆寫")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"meta": {"updated": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M"), "source": "臺灣證券交易所 OpenAPI"}, "stocks": stocks}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("完成:", len(stocks), "檔")


if __name__ == "__main__":
    main()
