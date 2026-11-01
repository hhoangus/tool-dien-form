import streamlit as st
import requests
import re
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import random
import time

st.set_page_config(
    page_title="Smart Survey Generator",
    page_icon="📊",
    layout="wide"
)


def extract_form_data(url):
    try:
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        hdr = {"User-Agent": ua}
        res = requests.get(url, headers=hdr, timeout=10)
        if res.status_code != 200:
            return None, "Không thể mở link Form."

        pat = r'FB_PUBLIC_LOAD_DATA_\s*=\s*(\[.*?\]);\s*</script>'
        m = re.search(pat, res.text, re.DOTALL)
        if not m:
            return None, "Hãy dùng link viewform."

        raw = json.loads(m.group(1))
        title = "Khảo sát Google Form"
        if len(raw[1]) > 8 and raw[1][8]:
            title = raw[1][8]
        q_raw = raw[1][1]

        qs = []
        pages = 1
        for q in q_raw:
            if not q or len(q) < 4:
                continue
            q_title = str(q[1]).strip()
            q_type = q[3]

            if q_type == 8:
                pages += 1
                continue

            if not q[4] or not isinstance(q[4], list):
                continue
            if len(q[4]) == 0:
                continue

            info = q[4][0]
            eid = f"entry.{info[0]}"
            opts_raw = info[1]

            opts = []
            if opts_raw and isinstance(opts_raw, list):
                for o in opts_raw:
                    if o and len(o) > 0 and o[0] != "":
                        opts.append(str(o[0]))

            l_set = {'1', '2', '3', '4', '5', '6', '7'}
            if q_type in [2, 3, 4, 5] and opts:
                is_l = (q_type == 5)
                if set(opts).issubset(l_set):
                    is_l = True
                qs.append({
                    "title": q_title,
                    "type": q_type,
                    "entry_id": eid,
                    "options": opts,
                    "is_likert": is_l
                })
            elif q_type in [0, 1]:
                qs.append({
                    "title": q_title,
                    "type": q_type,
                    "entry_id": eid,
                    "options": ["Tự luận"],
                    "is_likert": False
                })

        s_url = res.url.split('?')[0]
        if s_url.endswith('/viewform'):
            s_url = s_url[:-9] + '/formResponse'
        elif not s_url.endswith('/formResponse'):
            s_url = s_url.rstrip('/') + '/formResponse'

        return {
            "title": title,
            "submit_url": s_url,
            "page_count": pages,
            "questions": qs
        }, None
    except Exception as e:
        return None, f"Lỗi: {str(e)}"


def calc_alpha(df_l):
    if df_l.shape[1] < 2:
        return 0.0
    scores = df_l.values.astype(float)
    i_vars = scores.var(axis=0, ddof=1)
    t_scores = scores.sum(axis=1)
    k = df_l.shape[1]
    t_var = t_scores.var(ddof=1)
    if t_var == 0:
        return 0.0
    p1 = k / (k - 1.0)
    p2 = 1.0 - (i_vars.sum() / t_var)
    return round(float(p1 * p2), 3)


def gen_timestamps(n, days=5):
    ts = []
    now = datetime.now()
    hw = [
        1, 1, 0, 0, 0, 1, 2, 5, 8, 10, 10, 8,
        6, 7, 9, 10, 8, 7, 8, 10, 12, 12, 8, 3
    ]
    for _ in range(n):
        d = now - timedelta(days=random.randint(0, days))
        h = random.choices(range(24), weights=hw, k=1)[0]
        m = random.randint(0, 59)
        s = random.randint(0, 59)
        dt = d.replace(hour=h, minute=m, second=s)
        if dt > now:
            dt = now - timedelta(minutes=random.randint(5, 90))
        ts.append(dt)
    ts.sort()
    fmt = "%Y/%m/%d %I:%M:%S %p GMT+7"
    return [dt.strftime(fmt) for dt in ts]


st.title("📊 Smart Survey Synthetic Generator")
st.caption(
    "👨‍💻 **Phát triển bởi:** Hoàng (FIT - HCMUS) | "
    "Công cụ tạo dữ liệu khảo sát chuẩn SPSS / SmartPLS "
    "dành cho tiểu luận & nghiên cứu khoa học."
)

with st.expander("📖 Hướng dẫn sử dụng nhanh"):
    st.markdown(
        "1. **Cài đặt Form:** Tắt *Giới hạn 1 lần trả lời* "
        "và tắt *Thu thập email* trong Google Form.\n"
        "2. **Bước 1:** Dán link `.../viewform` vào ô dưới.\n"
        "3. **Bước 2:** Chọn số lượng mẫu và chia nhóm nhân tố.\n"
        "4. **Bước 3:** Bấm **Sinh dữ liệu**, kiểm tra Alpha "
        "rồi chọn **Tải file CSV** hoặc **Tự động điền**."
    )

u_in = st.text_input(
    "🔗 Bước 1: Dán link Google Form (viewform) vào đây:"
)

if u_in:
    with st.spinner("Đang đọc cấu trúc Google Form..."):
        f_data, err = extract_form_data(u_in)

    if err:
        st.error(err)
    elif f_data:
        q_cnt = len(f_data['questions'])
        st.success(f"Đã tải: **{f_data['title']}** ({q_cnt} câu)")

        st.divider()
        st.subheader("⚙️ Bước 2: Thiết lập Mô hình & Kịch bản")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            n_sam = st.number_input(
                "Số lượng mẫu:", 20, 1000, 200, 10
            )
        with c2:
            n_fac = st.number_input(
                "Số nhân tố độc lập (X):", 1, 8, 3, 1
            )
        with c3:
            cons = st.slider(
                "Độ gắn kết (Alpha):", 0.70, 0.95, 0.84, 0.01
            )
        with c4:
            reg_s = st.slider(
                "Tác động X -> Y:", 0.30, 0.90, 0.65, 0.05
            )

        f_opts = [f"Nhân tố X{k+1}" for k in range(n_fac)]
        f_opts.append("Biến phụ thuộc Y")

        l_qs = [q for q in f_data['questions'] if q['is_likert']]
        o_qs = [q for q in f_data['questions'] if not q['is_likert']]

        q_f_map = {}
        rev_map = {}
        f_means = {}

        if l_qs:
            with st.expander("🧩 Phân nhóm câu hỏi Thang đo", True):
                st.markdown("**1. Điểm trung bình (Mean) từng nhóm:**")
                f_cols = st.columns(len(f_opts))
                for idx, fn in enumerate(f_opts):
                    with f_cols[idx]:
                        f_means[fn] = st.slider(
                            fn, 2.0, 4.6, 3.8, 0.1,
                            key=f"m_{idx}"
                        )

                st.markdown("**2. Gán câu hỏi vào nhóm nhân tố:**")
                tot_l = len(l_qs)
                for idx, q in enumerate(l_qs):
                    d_i = int(idx * len(f_opts) / tot_l)
                    d_idx = min(d_i, len(f_opts) -
