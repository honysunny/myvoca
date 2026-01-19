import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import google.generativeai as genai

# 1. 페이지 설정
st.set_page_config(page_title="심층 영단어장", page_icon="📚")
st.title("📚 AI 심층 영단어장 (다의어 학습)")

# 2. Gemini 설정
try:
    genai.configure(api_key=st.secrets["gemini"]["api_key"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error(f"Gemini 설정 오류: {e}")

# 3. 구글 시트 연결 (날짜 빼고 3개 컬럼만!)
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # A, B, C열만 가져옴 (날짜 없음)
    existing_data = conn.read(worksheet="Sheet1", usecols=[0, 1, 2], ttl=0)
    existing_data = existing_data.dropna(how="all")
except:
    existing_data = pd.DataFrame(columns=["단어", "뜻", "예문"])

# 4. 입력 폼
with st.form("input_form", clear_on_submit=False):
    word = st.text_input("영단어 입력", placeholder="예: hold")
    
    # 🌟 AI 다의어 분석 로직
    if st.form_submit_button("🔍 AI로 여러 뜻 분석하기"):
        if word:
            with st.spinner(f"'{word}'의 다양한 뜻을 분석 중..."):
                try:
                    # 프롬프트: 여러 뜻을 줄바꿈으로 구분해서 달라고 요청
                    prompt = f"""
                    영단어 '{word}'의 가장 자주 쓰이는 핵심 뜻을 최대 3개까지 찾아줘.
                    각 뜻마다 그에 맞는 영어 예문을 하나씩 작성해줘.
                    
                    반드시 아래 형식(파이프 | 로 구분)을 지켜서 출력해:
                    1. 뜻1 | 예문1
                    2. 뜻2 | 예문2
                    3. 뜻3 | 예문3
                    """
                    response = model.generate_content(prompt)
                    
                    # 결과 텍스트를 줄 단위로 쪼개기
                    raw_lines = response.text.strip().split('\n')
                    
                    meanings_list = []
                    examples_list = []
                    
                    for line in raw_lines:
                        if "|" in line:
                            # 파이프(|) 기준으로 앞은 뜻, 뒤는 예문으로 나눔
                            m, e = line.split("|", 1)
                            meanings_list.append(m.strip()) # 뜻 리스트에 추가
                            examples_list.append(e.strip()) # 예문 리스트에 추가
                    
                    # 화면에 보여주기 위해 줄바꿈 문자로 합치기
                    st.session_state['generated_meaning'] = '\n'.join(meanings_list)
                    st.session_state['generated_example'] = '\n'.join(examples_list)
                    
                except Exception as e:
                    st.error(f"AI 검색 실패: {e}")
        else:
            st.warning("단어를 먼저 입력하세요!")

    # 5. 결과 확인 및 저장 (Text Area 사용)
    if "generated_meaning" in st.session_state:
        st.write("---")
        st.info("💡 뜻이 여러 개면 줄바꿈으로 구분됩니다.")
        
        col1, col2 = st.columns(2)
        with col1:
            # text_area는 여러 줄 입력이 가능합니다
            final_meaning = st.text_area("뜻 (여러 개 가능)", value=st.session_state['generated_meaning'], height=150)
        with col2:
            final_example = st.text_area("예문 (뜻과 순서 맞춤)", value=st.session_state['generated_example'], height=150)

        if st.form_submit_button("💾 구글 시트에 저장하기"):
            new_entry = pd.DataFrame([{
                "단어": word,
                "뜻": final_meaning,
                "예문": final_example
            }])
            
            updated_data = pd.concat([existing_data, new_entry], ignore_index=True)
            conn.update(worksheet="Sheet1", data=updated_data)
            
            st.success(f"'{word}' 저장 완료!")
            del st.session_state['generated_meaning']
            del st.session_state['generated_example']
            st.cache_data.clear()
            st.rerun()

# 6. 목록 보여주기
st.divider()
st.subheader("📝 저장된 단어장")
st.dataframe(existing_data.iloc[::-1], use_container_width=True)