from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from joinpreflight.relationship_matrix import build_order_features,select_features,analyze_and_plot


def make_csvs(tmp_path: Path, n=120):
    ids=[f"{i:04d}" for i in range(n)]
    orders=pd.DataFrame({"order_id":ids,
        "order_purchase_timestamp":pd.date_range("2025-01-01",periods=n,freq="D"),
        "order_delivered_customer_date":pd.date_range("2025-01-01",periods=n,freq="D")+pd.to_timedelta(np.arange(n)%19+2,unit="D"),
        "order_estimated_delivery_date":pd.date_range("2025-01-01",periods=n,freq="D")+pd.to_timedelta(15,unit="D")})
    items=[];payments=[]
    for i,key in enumerate(ids):
        for j in range(i%9+1):
            items.append({"order_id":key,"price":float(20+i%17+j),"freight_value":float((i+j)%9+1)})
        payments.append({"order_id":key,"payment_value":float(25+i%43*7),
                         "payment_installments":int(i%10+1),"payment_type":"credit_card"})
    files=[]
    for name,table in [("orders",orders),("items",pd.DataFrame(items)),("payments",pd.DataFrame(payments))]:
        f=tmp_path/f"{name}.csv";table.to_csv(f,index=False);files.append(f)
    return files


def test_order_grain_and_preserve_leading_zeros(tmp_path):
    o,i,p=make_csvs(tmp_path)
    f=build_order_features(o,i,p)
    assert len(f)==120 and f.order_id.iloc[0]=="0000"
    assert f.item_count.iloc[0]==1 and f.item_count.iloc[8]==9
    assert "delivery_days" in f and "payment_total" in f


def test_dynamic_selection_and_export(tmp_path):
    files=make_csvs(tmp_path)
    dst=tmp_path/"matrix.png"
    meta=analyze_and_plot(*files,dst,max_features=6,max_points=150)
    assert 2<=meta["n"]<=6
    assert "overcount_amount" not in meta["features"]
    assert dst.exists() and dst.with_suffix(".svg").exists()
    assert (tmp_path/"matrix_candidate_audit.csv").exists()
    assert (tmp_path/"matrix_metadata.json").exists()


def test_reject_duplicate_order_keys(tmp_path):
    o,i,p=make_csvs(tmp_path)
    df=pd.read_csv(o,dtype={"order_id":"string"})
    df.loc[1,"order_id"]=df.loc[0,"order_id"]
    df.to_csv(o,index=False)
    with pytest.raises(ValueError,match="unique"):
        build_order_features(o,i,p)


def test_redundancy_excludes_second_feature():
    x=np.arange(120)
    frame=pd.DataFrame({"item_count":x+1,"payment_total":x*2+13,
                       "freight_total":np.random.default_rng(1).uniform(1,100,120)})
    chosen,audit=select_features(frame,max_features=7)
    assert "item_count" in chosen
    assert "payment_total" not in chosen
    assert "near-duplicate" in audit.set_index("feature").loc["payment_total","reason"]
