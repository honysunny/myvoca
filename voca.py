import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import google.generativeai as genai

# 1. 페이지 설정
st.set_page_config(page_title="완전체 영단어장", page_icon="🎓")
st.title("🎓 AI 영단어장 (안전장치 추가)")

# 2. Gemini 설정
try:
    genai.configure(api_key=st.secrets["gemini"]["api_key"])
    model = genai.GenerativeModel('gemini-2.5-flash')
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
            else:
                with st.spinner(f"'{target_word}' 분석 중..."):
                    try:
                        prompt = f"""
                        영단어 '{target_word}'의 가장 자주 쓰이는 핵심 뜻을 최대 3개까지 찾아줘.
                        각 뜻마다 그에 맞는 영어 예문을 하나씩 작성해줘.
                        형식: 뜻 | 예문 (줄바꿈)
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
    
    raw_lines = raw_text.strip().split('\n')
    meanings_list = []
    examples_list = []
    for line in raw_lines:
        if "|" in line:
            m, e = line.split("|", 1)
            meanings_list.append(m.strip())
            examples_list.append(e.strip())
    
    default_meaning = '\n'.join(meanings_list)
    default_example = '\n'.join(examples_list)

    st.info(f"🧐 '{target_word}' 분석 결과입니다. 확인 후 추가하세요.")
    
    with st.container():
        col1, col2 = st.columns(2)
        with col1:
            final_meaning = st.text_area("뜻 확인", value=default_meaning, height=120)
        with col2:
            final_example = st.text_area("예문 확인", value=default_example, height=120)

        if st.button("💾 단어장에 추가하기", type="primary"):
            new_entry = pd.DataFrame([{
                "단어": target_word,
                "뜻": final_meaning,
                "예문": final_example
            }])
            updated_data = pd.concat([existing_data, new_entry], ignore_index=True)
            conn.update(worksheet="Sheet1", data=updated_data)
            
            st.toast("정상적으로 추가되었습니다. 🎉")
            del st.session_state['analyzed_word']
            del st.session_state['analyzed_result']
            st.cache_data.clear()
            st.rerun()

# 6. 목록 보여주기 (디자인 수정 & 삭제 안전장치)
st.divider()
st.subheader(f"📝 저장된 단어장 ({len(existing_data)}개)")

if not existing_data.empty:
    for i in sorted(existing_data.index, reverse=True):
        row = existing_data.loc[i]
        
        with st.expander(f"📖 {row['단어']}"):
            # 1. 라벨을 심플하게 '뜻', '예문'으로 변경
            new_meaning = st.text_area("뜻", value=row['뜻'], key=f"mean_{i}", height=100)
            new_example = st.text_area("예문", value=row['예문'], key=f"ex_{i}", height=100)
            
            c1, c2 = st.columns([1, 1])
            
            with c1:
                if st.button("💾 수정사항 반영", key=f"save_{i}"):
                    existing_data.at[i, "뜻"] = new_meaning
                    existing_data.at[i, "예문"] = new_example
                    conn.update(worksheet="Sheet1", data=existing_data)
                    st.toast(f"✅ '{row['단어']}' 수정되었습니다!")
                    st.rerun()
            
            with c2:
                # 2. 삭제 안전장치 로직 (Confirm 기능)
                # 각 단어마다 '삭제 버튼 눌렀는지' 상태를 기억해야 함
                delete_state_key = f"del_confirm_{i}"
                if delete_state_key not in st.session_state:
                    st.session_state[delete_state_key] = False

                if not st.session_state[delete_state_key]:
                    # 평소에는 휴지통 버튼만 보임
                    if st.button("🗑️ 삭제", key=f"del_btn_{i}"):
                        st.session_state[delete_state_key] = True
                        st.rerun()
                else:
                    # 휴지통 누르면 -> '진짜 삭제?' 물어보는 빨간 버튼들 등장
                    st.warning("정말 삭제하시겠습니까?")
                    col_del_yes, col_del_no = st.columns(2)
                    with col_del_yes:
                        if st.button("✅ 예", key=f"yes_{i}"):
                            updated_data = existing_data.drop(index=i)
                            conn.update(worksheet="Sheet1", data=updated_data)
                            st.toast(f"👋 '{row['단어']}' 삭제되었습니다!")
                            st.rerun()
                    with col_del_no:
                        if st.button("❌ 아니오", key=f"no_{i}"):
                            st.session_state[delete_state_key] = False
                            st.rerun()
else:
    st.info("아직 단어가 없어요. 위에서 검색해서 추가해보세요!")