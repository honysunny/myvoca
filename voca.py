import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import google.generativeai as genai

st.set_page_config(page_title="나만의 단어장", page_icon="🦁", layout="wide")
st.title("🦁 AI 영단어장 (Final Fix)")

# 🌟 Gemini 연결 (무적의 자동 탐지 로직)
try:
    if "gemini" in st.secrets and "api_key" in st.secrets["gemini"]:
        genai.configure(api_key=st.secrets["gemini"]["api_key"])
        
        # 1. 서버에 있는 모든 모델 목록을 가져옵니다.
        all_models = [m.name for m in genai.list_models()]
        
        # 2. 우리가 원하는 모델을 순서대로 찾습니다.
        # (1.5 Flash -> 1.0 Pro -> 그냥 Pro)
        target_model = None
        for candidate in ['gemini-1.5-flash', 'gemini-1.5-flash-latest', 'gemini-1.0-pro', 'gemini-pro']:
            for m in all_models:
                if candidate in m:
                    target_model = m
                    break
            if target_model: break
            
        if target_model:
            model = genai.GenerativeModel(target_model)
            # st.toast(f"연결된 모델: {target_model}") # (확인용, 나중에 삭제 가능)
        else:
            st.error("사용 가능한 모델을 찾지 못했습니다. (gemini-pro 등)")
            model = None
            
    else:
        st.error("🚨 API 키 설정을 확인해주세요.")
        model = None
except Exception as e:
    st.error(f"설정 오류: {e}")

# 3. 구글 시트 연결
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df = conn.read(worksheet="Sheet1", usecols=[0, 1, 2], ttl=0)
    # 데이터가 비었을 때 처리
    if not df.empty:
        df = df.dropna(how="all")
        existing_words = df["단어"].astype(str).tolist()
    else:
        existing_words = []
except:
    existing_words = []

# 4. 검색 및 저장 UI
with st.form("search"):
    word = st.text_input("단어 입력", placeholder="예: epiphany")
    submitted = st.form_submit_button("🔍 분석")
    
    if submitted and word:
        if word in existing_words:
            st.warning("이미 있는 단어입니다.")
        elif not model:
            st.error("AI 모델 연결 실패")
        else:
            try:
                # 간단 명료한 프롬프트
                prompt = f"Word: {word}\nFormat: Meaning | Example sentence (Simple English)"
                res = model.generate_content(prompt).text
                
                if "|" in res:
                    mean, ex = res.split("|", 1)
                else:
                    mean, ex = res, ""
                    
                st.session_state['new'] = {'w': word, 'm': mean.strip(), 'e': ex.strip()}
            except Exception as e:
                st.error(f"분석 실패: {e}")

# 저장 버튼
if 'new' in st.session_state:
    st.info(f"**{st.session_state['new']['w']}**")
    m = st.text_area("뜻", st.session_state['new']['m'])
    e = st.text_area("예문", st.session_state['new']['e'])
    
    if st.button("💾 저장"):
        try:
            # 기존 데이터 읽기
            current_df = conn.read(worksheet="Sheet1", usecols=[0,1,2])
            # 새 데이터 만들기
            new_row = pd.DataFrame([{'단어':st.session_state['new']['w'], '뜻':m, '예문':e}])
            # 합치기
            updated_df = pd.concat([current_df, new_row], ignore_index=True)
            # 업데이트
            conn.update(worksheet="Sheet1", data=updated_df)
            
            st.success("저장 완료!")
            del st.session_state['new']
            st.rerun()
        except Exception as e:
            st.error(f"저장 중 오류: {e}")

st.divider()
if existing_words:
    st.write(f"📚 저장된 단어 ({len(existing_words)}개): {', '.join(existing_words[:5])}...")