import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import google.generativeai as genai

# 1. 페이지 설정
st.set_page_config(page_title="완전체 영단어장", page_icon="🎓", layout="wide")
st.title("🎓 AI 영단어장 (Final Fix)")

# 2. Gemini 설정
try:
    if "gemini" in st.secrets and "api_key" in st.secrets["gemini"]:
        genai.configure(api_key=st.secrets["gemini"]["api_key"])
        model = genai.GenerativeModel('gemini-2.5-flash')
    else:
        st.error("🚨 Secrets에 API 키가 없습니다.")
        model = None
except Exception as e:
    st.error(f"Gemini 설정 오류: {e}")

# 3. 구글 시트 연결
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    existing_data = conn.read(worksheet="Sheet1", usecols=[0, 1, 2], ttl=0)
    existing_data = existing_data.dropna(how="all")
    if not existing_data.empty:
        existing_words = existing_data["단어"].astype(str).str.strip().tolist()
    else:
        existing_words = []
except:
    existing_data = pd.DataFrame(columns=["단어", "뜻", "예문"])
    existing_words = []

# 4. 입력 및 분석
with st.expander("🔍 단어 분석 및 추가", expanded=True):
    with st.form("search_form", clear_on_submit=True):
        col_input, col_btn = st.columns([4, 1])
        with col_input:
            word_input = st.text_input("영단어 입력 (엔터로 분석)", placeholder="예: epiphany")
        with col_btn:
            search_submitted = st.form_submit_button("🔍 분석")

        if search_submitted and word_input:
            target_word = word_input.strip()
            
            if target_word in existing_words:
                st.error(f"⚠️ '{target_word}'는 이미 단어장에 있습니다!")
                if 'analyzed_word' in st.session_state:
                    del st.session_state['analyzed_word']
            elif not model:
                st.error("AI 모델 연결 실패")
            else:
                with st.spinner(f"AI가 '{target_word}'를 분석 중..."):
                    try:
                        # [핵심 수정] 순서가 뒤집히지 않도록 예시를 박아넣었습니다.
                        prompt = f"""
                        Role: Korean-English Dictionary
                        Target Word: '{target_word}'
                        
                        Task:
                        1. Provide 1-3 common meanings in Korean.
                        2. Write a simple English example sentence for each.
                        
                        Format Rule:
                        Korean Meaning | English Example Sentence
                        
                        Example Output:
                        직관 | She had a sudden intuition.
                        깨닫다 | He realized the truth.
                        """
                        response = model.generate_content(prompt)
                        st.session_state['analyzed_word'] = target_word
                        st.session_state['analyzed_result'] = response.text
                    except Exception as e:
                        st.error(f"오류 발생: {e}")

# 5. 분석 결과 확인 및 저장
if 'analyzed_word' in st.session_state:
    target_word = st.session_state['analyzed_word']
    raw_text = st.session_state['analyzed_result']
    
    meanings_list = []
    examples_list = []
    
    # 결과 파싱
    for line in raw_text.strip().split('\n'):
        if "|" in line:
            parts = line.split("|", 1)
            # 확실하게 앞부분을 뜻, 뒷부분을 예문으로 가져옵니다.
            meanings_list.append(parts[0].strip())
            examples_list.append(parts[1].strip())
    
    default_meaning = '\n'.join(meanings_list)
    default_example = '\n'.join(examples_list)

    st.info(f"🧐 '{target_word}' 분석 결과")
    
    with st.container():
        col1, col2 = st.columns(2)
        with col1:
            final_meaning = st.text_area("🇰🇷 뜻 (한국어)", value=default_meaning, height=150)
        with col2:
            final_example = st.text_area("🇺🇸 예문 (영어)", value=default_example, height=150)

        if st.button("💾 단어장에 추가하기", type="primary", use_container_width=True):
            if not final_meaning or not final_example:
                st.warning("내용이 비어있습니다.")
            else:
                try:
                    # 기존 데이터 다시 읽기 (충돌 방지)
                    current_df = conn.read(worksheet="Sheet1", usecols=[0, 1, 2], ttl=0)
                    new_entry = pd.DataFrame([{
                        "단어": target_word,
                        "뜻": final_meaning,
                        "예문": final_example
                    }])
                    updated_data = pd.concat([current_df, new_entry], ignore_index=True)
                    conn.update(worksheet="Sheet1", data=updated_data)
                    
                    st.toast("저장 성공! 🎉")
                    del st.session_state['analyzed_word']
                    st.rerun()
                except Exception as e:
                    st.error(f"저장 중 오류가 발생했습니다. (requirements.txt에 gspread 확인 필요)\n에러: {e}")

# 6. 목록 보여주기
st.divider()
st.subheader(f"📝 저장된 단어장 ({len(existing_data)}개)")

if not existing_data.empty:
    for i in sorted(existing_data.index, reverse=True):
        row = existing_data.loc[i]
        with st.expander(f"📖 {row['단어']}"):
            c1, c2 = st.columns(2)
            with c1:
                new_meaning = st.text_area("뜻", row['뜻'], key=f"m_{i}")
            with c2:
                new_example = st.text_area("예문", row['예문'], key=f"e_{i}")
            
            if st.button("🗑️ 삭제", key=f"del_{i}"):
                updated_data = existing_data.drop(index=i)
                conn.update(worksheet="Sheet1", data=updated_data)
                st.rerun()
else:
    st.info("단어를 검색해서 추가해보세요!")