import streamlit as st
import requests
import re
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import random
import time
import streamlit as st

# --- CƠ CHẾ BẢO MẬT BẰNG MẬT KHẨU ---
PASSWORD = "123"  # Bạn có thể đổi thành mật khẩu tùy ý ở đây

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 Khu vực hạn chế")
    pwd = st.text_input("Nhập mật khẩu để truy cập công cụ:", type="password")
    if st.button("Xác nhận"):
        if pwd == PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Sai mật khẩu! Vui lòng hỏi lại tác giả.")
    st.stop()  # Dừng không cho chạy phần code bên dưới nếu chưa nhập đúng mật khẩu
st.set_page_config(
    page_title="Smart Survey Generator",
    page_icon="📊",
    layout="wide"
)


def extract_form(url):
    try:
        h = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(
            url, headers=h, timeout=10
        )
        if r.status_code != 200:
            return None, "Lỗi mở link Form."
        p = (
            r'FB_PUBLIC_LOAD_DATA_\s*=\s*'
            r'(\[.*?\]);\s*</script>'
        )
        m = re.search(p, r.text, re.DOTALL)
        if not m:
            return None, "Dùng link viewform."
        raw = json.loads(m.group(1))
        t = "Khảo sát Google Form"
        if len(raw[1]) > 8 and raw[1][8]:
            t = raw[1][8]
        qs = []
        pg = 1
        for q in raw[1][1]:
            if not q or len(q) < 4:
                continue
            qt = str(q[1]).strip()
            tp = q[3]
            if tp == 8:
                pg += 1
                continue
            if not q[4]:
                continue
            if not isinstance(q[4], list):
                continue
            if len(q[4]) == 0:
                continue
            inf = q[4][0]
            eid = f"entry.{inf[0]}"
            ops = []
            if inf[1]:
                for o in inf[1]:
                    if o and o[0] != "":
                        ops.append(str(o[0]))
            ls = {'1', '2', '3', '4', '5', '6', '7'}
            if tp in [2, 3, 4, 5] and ops:
                il = (tp == 5)
                if set(ops).issubset(ls):
                    il = True
                qs.append({
                    "title": qt,
                    "type": tp,
                    "entry_id": eid,
                    "options": ops,
                    "is_likert": il
                })
            elif tp in [0, 1]:
                qs.append({
                    "title": qt,
                    "type": tp,
                    "entry_id": eid,
                    "options": ["Tự luận"],
                    "is_likert": False
                })
        su = r.url.split('?')[0]
        if su.endswith('/viewform'):
            su = su[:-9] + '/formResponse'
        else:
            su = su.rstrip('/')
            su = su + '/formResponse'
        return {
            "title": t,
            "submit_url": su,
            "page_count": pg,
            "questions": qs
        }, None
    except Exception as e:
        return None, f"Lỗi: {str(e)}"


def calc_alpha(df_l):
    if df_l.shape[1] < 2:
        return 0.0
    s = df_l.values.astype(float)
    iv = s.var(axis=0, ddof=1).sum()
    tv = s.sum(axis=1).var(ddof=1)
    if tv == 0:
        return 0.0
    k = df_l.shape[1]
    a = (k / (k - 1.0)) * (1.0 - iv / tv)
    return round(float(a), 3)


def gen_ts(n):
    ts = []
    now = datetime.now()
    hw = [
        1, 1, 0, 0, 0, 1, 2, 5,
        8, 10, 10, 8, 6, 7, 9, 10,
        8, 7, 8, 10, 12, 12, 8, 3
    ]
    for _ in range(n):
        d = random.randint(0, 5)
        dt = now - timedelta(days=d)
        h = random.choices(
            range(24), weights=hw, k=1
        )[0]
        m = random.randint(0, 59)
        s = random.randint(0, 59)
        dt = dt.replace(
            hour=h, minute=m, second=s
        )
        if dt > now:
            rm = random.randint(5, 90)
            dt = now - timedelta(minutes=rm)
        ts.append(dt)
    ts.sort()
    f = "%Y/%m/%d %I:%M:%S %p GMT+7"
    return [x.strftime(f) for x in ts]


st.title("📊 Smart Survey Generator")
st.caption(
    "👨‍💻 **Phát triển bởi:** Hoàng (FIT - HCMUS)"
    " | Công cụ tạo dữ liệu khảo sát chuẩn "
    "SPSS / SmartPLS cho tiểu luận & NCKH."
)

with st.expander("📖 Hướng dẫn sử dụng"):
    st.markdown(
        "1. **Cài đặt Form:** Tắt *Giới hạn 1 "
        "lần trả lời* và tắt *Thu thập email*.\n"
        "2. **Bước 1:** Dán link `viewform`.\n"
        "3. **Bước 2:** Chọn số mẫu & chia nhóm.\n"
        "4. **Bước 3:** Bấm **Sinh dữ liệu**, "
        "tải **File CSV** hoặc **Tự động điền**."
    )

u_in = st.text_input(
    "🔗 Bước 1: Dán link Google Form (viewform):"
)

if u_in:
    fd, err = extract_form(u_in)
    if err:
        st.error(err)
    elif fd:
        qc = len(fd['questions'])
        st.success(
            f"Đã tải: **{fd['title']}** ({qc} câu)"
        )
        c1, c2, c3, c4 = st.columns(4)
        n_s = c1.number_input(
            "Số lượng mẫu:", 20, 1000, 200, 10
        )
        n_f = c2.number_input(
            "Số nhân tố X:", 1, 8, 3, 1
        )
        con = c3.slider(
            "Độ gắn kết Alpha:",
            0.70, 0.95, 0.84, 0.01
        )
        reg = c4.slider(
            "Tác động X -> Y:",
            0.30, 0.90, 0.65, 0.05
        )

        f_ops = [
            f"Nhân tố X{k+1}"
            for k in range(n_f)
        ]
        f_ops.append("Biến phụ thuộc Y")

        l_qs = [
            q for q in fd['questions']
            if q['is_likert']
        ]
        o_qs = [
            q for q in fd['questions']
            if not q['is_likert']
        ]
        q_map = {}
        r_map = {}
        f_ms = {}
        c_ws = {}
        c_tx = {}

        if l_qs:
            with st.expander(
                "🧩 Phân nhóm câu hỏi Thang đo",
                True
            ):
                fcs = st.columns(len(f_ops))
                for i, fn in enumerate(f_ops):
                    f_ms[fn] = fcs[i].slider(
                        fn, 2.0, 4.6, 3.8, 0.1,
                        key=f"m_{i}"
                    )
                tl = len(l_qs)
                fo_len = len(f_ops)
                for i, q in enumerate(l_qs):
                    di = int(i * fo_len / tl)
                    if di >= fo_len:
                        di = fo_len - 1
                    cq, cf, cr = st.columns(
                        [5, 3, 2]
                    )
                    eid = q['entry_id']
                    cq.markdown(
                        f"**Câu {i+1}:** "
                        f"{q['title']}"
                    )
                    q_map[eid] = cf.selectbox(
                        "Nhóm", f_ops, index=di,
                        key=f"fs_{eid}",
                        label_visibility="collapsed"
                    )
                    r_map[eid] = cr.checkbox(
                        "Đảo chiều",
                        key=f"rv_{eid}"
                    )

        if o_qs:
            with st.expander(
                "🎛️ Tỷ lệ Nhân khẩu học / Tự luận"
            ):
                for q in o_qs:
                    st.markdown(
                        f"**{q['title']}**"
                    )
                    eid = q['entry_id']
                    if q['type'] in [0, 1]:
                        dt = "Tốt; Khá; Bình thường"
                        stx = st.text_input(
                            "Câu mẫu (ngăn bởi ;):",
                            dt, key=f"tx_{eid}"
                        )
                        c_tx[eid] = [
                            x.strip()
                            for x in stx.split(";")
                            if x.strip()
                        ]
                    else:
                        ops = q['options']
                        ol = len(ops)
                        cls = st.columns(
                            min(ol, 6)
                        )
                        ws = []
                        dw = int(100 / ol)
                        for oi, op in enumerate(ops):
                            cl = cls[oi % len(cls)]
                            w = cl.number_input(
                                op, 0, 100, dw,
                                key=f"w_{eid}_{oi}"
                            )
                            ws.append(w)
                        tw = sum(ws)
                        if tw <= 0:
                            tw = 1
                        c_ws[eid] = [
                            w / tw for w in ws
                        ]

        if st.button(
            "🚀 Bước 3: Sinh dữ liệu & Kiểm định",
            type="primary"
        ):
            sn = max(0.18, (1.0 - con) * 1.6)
            lm = {}
            ifs = f_ops[:-1]
            df = f_ops[-1]
            for fn in ifs:
                fm = f_ms.get(fn, 3.8)
                lm[fn] = np.random.normal(
                    fm, 0.65, n_s
                )
            if ifs:
                mx = np.mean(
                    [lm[f] for f in ifs],
                    axis=0
                )
                ym = f_ms.get(df, 3.9)
                yb = np.random.normal(
                    ym, 0.65, n_s
                )
                lm[df] = (
                    reg * mx + (1.0 - reg) * yb
                )
            else:
                lm[df] = np.random.normal(
                    3.8, 0.65, n_s
                )

            ts_l = gen_ts(n_s)
            rows = []
            for i in range(n_s):
                rd = {"Dấu thời gian": ts_l[i]}
                for q in fd['questions']:
                    eid = q['entry_id']
                    ops = q['options']
                    qt = q['title']
                    if q['is_likert']:
                        fg = q_map.get(
                            eid, f_ops[0]
                        )
                        ns = np.random.normal(
                            0, sn
                        )
                        v = lm[fg][i] + ns
                        mn = int(ops[0])
                        mx = int(ops[-1])
                        cv = int(
                            np.clip(
                                np.round(v),
                                mn, mx
                            )
                        )
                        if r_map.get(eid, False):
                            cv = (mx + mn) - cv
                        rd[qt] = str(cv)
                    elif q['type'] in [0, 1]:
                        pl = c_tx.get(
                            eid, ["Bình thường"]
                        )
                        rd[qt] = random.choice(pl)
                    else:
                        ol = len(ops)
                        dp = [1 / ol] * ol
                        pr = c_ws.get(eid, dp)
                        if q['type'] == 4:
                            mk = min(3, ol)
                            kp = random.randint(
                                1, mk
                            )
                            pk = np.random.choice(
                                ops, size=kp,
                                replace=False,
                                p=pr
                            )
                            rd[qt] = ", ".join(pk)
                        else:
                            rd[qt] = (
                                np.random.choice(
                                    ops, p=pr
                                )
                            )
                rows.append(rd)
            st.session_state['dfr'] = (
                pd.DataFrame(rows)
            )
            st.session_state['qfm'] = q_map

        if 'dfr' in st.session_state:
            dfr = st.session_state['dfr']
            qfm = st.session_state['qfm']
            st.subheader(
                "📈 Kiểm định Cronbach's Alpha"
            )
            asum = []
            for fn in f_ops:
                cin = [
                    q['title'] for q in l_qs
                    if qfm.get(q['entry_id']) == fn
                ]
                if len(cin) >= 2:
                    av = calc_alpha(dfr[cin])
                    ok = (0.7 <= av <= 0.96)
                    st_t = (
                        "✅ Tốt" if ok
                        else "⚠️ Chỉnh lại"
                    )
                    asum.append({
                        "Nhóm": fn,
                        "Số câu": len(cin),
                        "Alpha": av,
                        "Đánh giá": st_t
                    })
            if asum:
                st.table(pd.DataFrame(asum))
            st.dataframe(
                dfr.head(10),
                use_container_width=True
            )
            d1, d2 = st.columns(2)
            csv_b = dfr.to_csv(
                index=False
            ).encode('utf-8-sig')
            d1.download_button(
                "📥 Tải File CSV chuẩn",
                csv_b,
                f"Survey_{n_s}.csv",
                "text/csv"
            )
            if d2.button("📨 Tự động điền Form"):
                pb = st.progress(0)
                stx = st.empty()
                pc = fd['page_count']
                ph = ",".join(
                    [str(p) for p in range(pc)]
                )
                okc = 0
                tr = len(dfr)
                for idx, row in dfr.iterrows():
                    pl = {"pageHistory": ph}
                    for q in fd['questions']:
                        eid = q['entry_id']
                        v = row[q['title']]
                        if q['type'] == 4:
                            pl[eid] = v.split(", ")
                        else:
                            pl[eid] = v
                    try:
                        rp = requests.post(
                            fd['submit_url'],
                            data=pl,
                            timeout=5
                        )
                        if rp.status_code == 200:
                            okc += 1
                    except Exception:
                        pass
                    pb.progress((idx + 1) / tr)
                    stx.text(
                        f"Gửi {idx+1}/{tr} "
                        f"(OK: {okc})"
                    )
                    sl = random.uniform(0.3, 0.8)
                    time.sleep(sl)
                st.success(
                    f"🎉 Đã điền {okc}/{tr} phiếu!"
                )
