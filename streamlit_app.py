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
    page_title="Smart Survey Generator Pro",
    page_icon="📊",
    layout="wide"
)

# --- 1. MODULE BOC TACH GOOGLE FORM ---
def extract_form_data(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None, "Không thể truy cập link Form."

        pattern = r'FB_PUBLIC_LOAD_DATA_\s*=\s*(\[.*?\]);\s*</script>'
        match = re.search(pattern, response.text, re.DOTALL)
        if not match:
            return None, "Không tìm thấy dữ liệu. Hãy dùng link viewform."

        raw_data = json.loads(match.group(1))
        form_title = "Khảo sát Google Form"
        if len(raw_data[1]) > 8 and raw_data[1][8]:
            form_title = raw_data[1][8]
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

            likert_set = {'1', '2', '3', '4', '5', '6', '7'}
            if q_type in [2, 3, 4, 5] and options:
                is_likert = (q_type == 5) or set(options).issubset(likert_set)
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


# --- 2. HAM TINH CRONBACH'S ALPHA ---
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
    alpha = (n_items / (n_items - 1.0)) * (1.0 - item_vars.sum() / total
