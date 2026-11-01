import streamlit as st
import requests
import re
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import random
import time

st.set_page_config(page_title="Smart Survey Generator Pro", page_icon="📊", layout="wide")

# --- 1. MODULE BÓC TÁCH GOOGLE FORM ---
def extract_form_data(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None, "Không thể truy cập link Form. Hãy kiểm tra lại quyền công khai của Form."

        match = re.search(r'FB_PUBLIC_LOAD_DATA_\s*=\s*(\[.*?\]);\s*</script>', response.text, re.DOTALL)
        if not match:
            return None, "Không tìm thấy cấu trúc dữ liệu. Hãy chắc chắn đây là link Google Form (viewform) hợp lệ."

        raw_data = json.loads(match.group(1))
        form_title = raw_data[1][8] if len(raw_data[1]) > 8 and raw_data[1][8] else "Khảo sát Google Form"
        questions_raw = raw_data[1][1]

        questions = []
        page_count = 1
        for q in questions_raw:
            if not q or len(q) < 4:
                continue
            q_title = str(q[1]).strip()
            q_type = q[3]
            
            if q_type == 8:
                page_count += 1
                continue

            if not q[4] or not isinstance(q[4], list) or len(q[4]) == 0:
                continue

            entry_info = q[4][0]
            entry_id = f"entry.{entry_info[0]}"
            options_raw = entry_info[1]

            options = []
            if options_raw and isinstance(options_raw, list):
                for opt in options_raw:
                    if opt and len(opt) > 0 and opt[0] != "":
                        options.append(str(opt[0]))

            # Hỗ trợ Trắc nghiệm (2), Dropdown (3), Checkbox (4), Thang đo (5), Tự luận ngắn (0), Đoạn văn (1)
            if q_type in [2, 3, 4, 5] and options:
                is_likert = (q_type == 5) or (set(options).issubset({'1', '2', '3', '4', '5', '6', '7'}))
                questions.append({
                    "title": q_title,
                    "type": q_type,
                    "entry_id": entry_id,
                    "options": options,
                    "is_likert": is_likert
                })
            elif q_type in [0, 1]:
                questions.append({
                    "title": q_title,
                    "type": q_type,
                    "entry_id": entry_id,
                    "options": ["Tự luận"],
                    "is_likert": False
                })

        submit_url = response.url.split('?')[0]
        if submit_url.endswith('/viewform'):
            submit_url = submit_url[:-9] + '/formResponse'
        elif not submit_url.endswith('/formResponse'):
            submit_url = submit_url.rstrip('/') + '/formResponse'

        return {
            "title": form_title,
            "submit_url": submit_url,
            "page_count": page_count,
            "questions": questions
        }, None
    except Exception as e:
        return None, f"Lỗi phân tích Form: {str(e)}"

# --- 2. HÀM TÍNH CRONBACH'S ALPHA ---
def calculate_cronbach_alpha(df_likert):
    if df_likert.shape[1] < 2:
        return 0.0
    item_scores = df_likert.values.astype(float)
    item_vars = item_scores.var(axis=0, ddof=1)
    t_scores = item_scores.sum(axis=1)
    n_items = df_likert.shape[1]
    total_var = t_scores.var(ddof=1)
    if total_var == 0:
        return 0.0
    alpha = (n_items / (n_items - 1.0)) * (1.0 - item_vars.sum() / total_var)
    return round(float(alpha), 3)

# --- 3. HÀM SINH THỜI GIAN TỰ NHIÊN ---
def generate_realistic_timestamps(n_samples, days_back=5):
    timestamps = []
    now = datetime.now()
    for _ in range(n_samples):
        random_day = now - timedelta(days=random.randint(0, days_back))
        hour = random.choices(
            population=list(range(24)),
            weights=[1,1,0,0,0,1,2,5,8,10,10,8,6,7,9,10,8,7,8,10,12,12,8,3],
            k=1
        )[0]
        dt = random_day.replace(hour=hour, minute=random.randint(0, 59), second=random.randint(0, 59))
        if dt > now:
            dt = now - timedelta(minutes=random.randint(5, 120))
        timestamps.append(dt)
    timestamps.sort()
    return [dt.strftime("%Y/%m/%d %I:%M:%S %p GMT+7") for dt in timestamps]

# --- GIAO DIỆN CHÍNH ---
st.title("📊 Smart Survey Synthetic Generator (Pro Edition)")
st.caption("Hỗ trợ gom nhóm Nhân tố (EFA), tối ưu Cronbach's Alpha & Hồi quy tuyến tính (SPSS / SmartPLS)")

url_input = st.text_input("🔗 Bước 1: Dán đường link Google Form (viewform) vào đây:", placeholder="https://docs.google.com/forms/d/e/.../viewform")

if url_input:
    with st.spinner("Đang bóc tách cấu trúc câu hỏi từ Google Form..."):
        form_data, error = extract_form_data(url_input)
    
    if error:
        st.error(error)
    elif form_data:
        st.success(f"Đã tải Form: **{form_data['title']}** (Tổng cộng {len(form_data['questions'])} câu hỏi)")
        
        st.divider()
        st.subheader("⚙️ Bước 2: Thiết lập Mô hình Nghiên cứu & Kịch bản")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            n_samples = st.number_input("Số lượng mẫu khảo sát:", min_value=20, max_value=1000, value=200, step=10)
        with col2:
            num_factors = st.number_input("Số nhóm nhân tố độc lập (X):", min_value=1, max_value=8, value=3, step=1)
        with col3:
            consistency = st.slider("Độ gắn kết trong từng nhóm (Alpha):", 0.70, 0.95, 0.84, 0.01)
        with col4:
            reg_strength = st.slider("Độ mạnh tác động X -> Y (Hồi quy):", 0.30, 0.90, 0.65, 0.05)

        factor_options = [f"Nhân tố độc lập X{k+1}" for k in range(num_factors)] + ["Biến phụ thuộc Y (Kết quả)"]
        
        likert_questions = [q for q in form_data['questions'] if q['is_likert']]
        other_questions = [q for q in form_data['questions'] if not q['is_likert']]

        # Cấu hình chia nhóm EFA cho câu hỏi thang đo
        question_factor_map = {}
        reverse_coded_map = {}
        factor_means = {}

        if likert_questions:
            with st.expander("🧩 Phân nhóm câu hỏi Thang đo để chạy chuẩn EFA & Hồi quy (Đã tự động chia đều sẵn)", expanded=True):
                st.info("💡 **Mẹo:** Hệ thống đã tự động chia đều các câu hỏi thang đo vào các nhóm X1, X2... và nhóm Y cuối cùng. Bạn có thể đổi lại cho khớp với bài tiểu luận của mình.")
                
                # Chỉnh điểm trung bình cho từng nhân tố
                st.markdown("**1. Xu hướng điểm trung bình (Mean) của từng nhóm nhân tố:**")
                f_cols = st.columns(len(factor_options))
                for f_idx, f_name in enumerate(factor_options):
                    with f_cols[f_idx]:
                        factor_means[f_name] = st.slider(f"{f_name}", 2.0, 4.6, 3.8, 0.1, key=f"mean_{f_idx}")

                st.markdown("**2. Gán từng câu hỏi vào nhóm nhân tố tương ứng:**")
                total_l = len(likert_questions)
                for idx, q in enumerate(likert_questions):
                    # Tự động gán chia đều các câu hỏi vào X1, X2... và Y
                    default_f_idx = min(int(idx * len(factor_options) / total_l), len(factor_options) - 1)
                    c_q, c_f, c_rev = st.columns([5, 3, 2])
                    with c_q:
                        st.markdown(f"**Câu {idx+1}:** {q['title']}")
                    with c_f:
                        chosen_f = st.selectbox("Nhóm:", factor_options, index=default_f_idx, key=f"f_sel_{q['entry_id']}", label_visibility="collapsed")
                        question_factor_map[q['entry_id']] = chosen_f
                    with c_rev:
                        is_rev = st.checkbox("Câu phủ định (Đảo chiều)", key=f"rev_{q['entry_id']}")
                        reverse_coded_map[q['entry_id']] = is_rev

        # Tuỳ chỉnh tỷ lệ câu hỏi nhân khẩu học & tự luận
        custom_weights = {}
        custom_texts = {}
        if other_questions:
            with st.expander("🎛️ Tinh chỉnh tỷ lệ câu hỏi Nhân khẩu học / Tự luận (Tuỳ chọn)", expanded=False):
                for idx, q in enumerate(other_questions):
                    st.markdown(f"**{q['title']}**")
                    if q['type'] in [0, 1]:
                        sample_txt = st.text_input(
                            "Nhập các câu trả lời mẫu (cách nhau bằng dấu chấm phẩy ; ):",
                            value="Rất tốt; Khá ổn; Cần cải thiện thêm; Không có ý kiến; Bình thường",
                            key=f"txt_{q['entry_id']}"
                        )
                        custom_texts[q['entry_id']] = [t.strip() for t in sample_txt.split(";") if t.strip()]
                    else:
                        cols = st.columns(min(len(q['options']), 6))
                        weights = []
                        for o_idx, opt in enumerate(q['options']):
                            with cols[o_idx % len(cols)]:
                                w = st.number_input(f"{opt}", min_value=0, max_value=100, value=int(100/len(q['options'])), key=f"w_{q['entry_id']}_{o_idx}")
                                weights.append(w)
                        total_w = sum(weights) if sum(weights) > 0 else 1
                        custom_weights[q['entry_id']] = [w / total_w for w in weights]

        # --- BƯỚC 3: THUẬT TOÁN SINH DỮ LIỆU ĐA NHÂN TỐ ---
        if st.button("🚀 Bước 3: Sinh dữ liệu & Chạy Kiểm định Cronbach's Alpha", type="primary"):
            sigma_latent = 0.65
            sigma_noise = max(0.18, (1.0 - consistency) * 1.6)

            # 1. Sinh biến ẩn độc lập cho các nhân tố X1, X2... (Đảm bảo phân tách rõ khi xoay EFA)
            latent_matrix = {}
            indep_factors = factor_options[:-1]
            dep_factor = factor_options[-1]

            for f_name in indep_factors:
                latent_matrix[f_name] = np.random.normal(factor_means.get(f_name, 3.8), sigma_latent, n_samples)

            # 2. Sinh biến ẩn phụ thuộc Y có tương quan hồi quy tuyến tính từ trung bình các biến X
            if indep_factors:
                mean_X = np.mean([latent_matrix[f] for f in indep_factors], axis=0)
                y_base = np.random.normal(factor_means.get(dep_factor, 3.9), sigma_latent, n_samples)
                latent_matrix[dep_factor] = reg_strength * mean_X + (1.0 - reg_strength) * y_base
            else:
                latent_matrix[dep_factor] = np.random.normal(3.8, sigma_latent, n_samples)

            timestamps = generate_realistic_timestamps(n_samples)
            generated_rows = []

            for i in range(n_samples):
                row_dict = {"Dấu thời gian": timestamps[i]}
                for q in form_data['questions']:
                    eid = q['entry_id']
                    if q['is_likert']:
                        f_group = question_factor_map.get(eid, factor_options[0])
                        z_score = latent_matrix[f_group][i]
                        raw_val = z_score + np.random.normal(0, sigma_noise)
                        
                        min_v, max_v = int(q['options'][0]), int(q['options'][-1])
                        clipped_val = int(np.clip(np.round(raw_val), min_v, max_v))
                        
                        # Xử lý câu hỏi đảo ngược
                        if reverse_coded_map.get(eid, False):
                            clipped_val = (max_v + min_v) - clipped_val
                            
                        row_dict[q['title']] = str(clipped_val)
                    elif q['type'] in [0, 1]:
                        txt_pool = custom_texts.get(eid, ["Không có ý kiến"])
                        row_dict[q['title']] = random.choice(txt_pool)
                    else:
                        probs = custom_weights.get(eid, [1/len(q['options'])]*len(q['options']))
                        if q['type'] == 4:
                            k_pick = random.randint(1, min(3, len(q['options'])))
                            picked = np.random.choice(q['options'], size=k_pick, replace=False, p=probs)
                            row_dict[q['title']] = ", ".join(picked)
                        else:
                            row_dict[q['title']] = np.random.choice(q['options'], p=probs)
                generated_rows.append(row_dict)

            st.session_state['df_result'] = pd.DataFrame(generated_rows)
            st.session_state['q_factor_map'] = question_factor_map

        # --- HIỂN THỊ KẾT QUẢ KIỂM ĐỊNH THEO TỪNG NHÓM ---
        if 'df_result' in st.session_state:
            df_res = st.session_state['df_result']
            q_f_map = st.session_state['q_factor_map']

            st.divider()
            st.subheader("📈 Bảng Kiểm định Độ tin cậy Cronbach's Alpha theo từng Nhân tố")

            alpha_summary = []
            for f_name in factor_options:
                cols_in_f = [q['title'] for q in likert_questions if q_f_map.get(q['entry_id']) == f_name]
                if len(cols_in_f) >= 2:
                    a_val = calculate_cronbach_alpha(df_res[cols_in_f])
                    status = "✅ Đạt chuẩn tốt (0.7 - 0.95)" if 0.7 <= a_val <= 0.96 else "⚠️ Cần chỉnh lại độ gắn kết"
                    alpha_summary.append({"Nhóm Nhân tố": f_name, "Số biến quan sát": len(cols_in_f), "Cronbach's Alpha": a_val, "Đánh giá SPSS": status})

            if alpha_summary:
                st.table(pd.DataFrame(alpha_summary))

            st.markdown("**Xem trước 10 dòng dữ liệu đầu tiên:**")
            st.dataframe(df_res.head(10), use_container_width=True)

            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                csv_data = df_res.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 Tải ngay File CSV chuẩn Google Form (Đưa vào SPSS/Excel ngay)",
                    data=csv_data,
                    file_name=f"Survey_Data_{n_samples}_samples.csv",
                    mime="text/csv",
                )
            with col_dl2:
                if st.button("📨 Tự động điền trực tiếp vào Google Form (Chế độ an toàn)"):
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    page_history = ",".join([str(p) for p in range(form_data['page_count'])])
                    
                    success_count = 0
                    for idx, row in df_res.iterrows():
                        payload = {"pageHistory": page_history}
                        for q in form_data['questions']:
                            val = row[q['title']]
                            if q['type'] == 4:
                                payload[q['entry_id']] = val.split(", ")
                            else:
                                payload[q['entry_id']] = val
                        try:
                            r = requests.post(form_data['submit_url'], data=payload, timeout=5)
                            if r.status_code == 200:
                                success_count += 1
                        except:
                            pass
                        progress_bar.progress((idx + 1) / len(df_res))
                        status_text.text(f"Đang gửi mẫu {idx+1}/{len(df_res)} (Thành công: {success_count})...")
                        time.sleep(random.uniform(0.3, 0.8))
                    st.success(f"🎉 Hoàn tất! Đã điền thành công {success_count}/{len(df_res)} phiếu vào Google Form.")