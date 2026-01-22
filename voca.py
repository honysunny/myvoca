import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import google.generativeai as genai
import re

# 1. 페이지 설정
st.set_page_config(page_title="완전체 영단어장", page_icon="🎓", layout="wide")
st.title("🎓 AI 영단어장 ")

# 2. Gemini 설정
try:
    if "gemini" in st.secrets and "api_key" in st.secrets["gemini"]:
        genai.configure(api_key=st.secrets["gemini"]["api_key"])
        # 사용자님이 찾아내신 최적의 모델 유지!
        model = genai.GenerativeModel('gemini-2.5-flash-lite')
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

# 탭 구성
tab1, tab2 = st.tabs(["📚 단어장 관리", "🧰 영어 공부 도구함"])

# ==========================================
# 탭 1: 단어장
# ==========================================
with tab1:
    with st.expander("🔍 단어/숙어 분석 및 추가", expanded=True):
        with st.form("search_form", clear_on_submit=True):
            col_input, col_btn = st.columns([4, 1])
            with col_input:
                word_input = st.text_input("단어 또는 숙어 입력", placeholder="예: address (명사/동사 뜻 모두 확인)")
            with col_btn:
                search_submitted = st.form_submit_button("🔍 분석")

            if search_submitted and word_input:
                input_word = word_input.strip()
                
                if not model:
                    st.error("AI 모델 연결 실패")
                else:
                    with st.spinner(f"AI가 '{input_word}'의 다양한 품사와 뜻을 분석 중..."):
                        try:
                            # 품사(POS) 구분 프롬프트 유지
                            prompt = f"""
                            Role: Comprehensive English-Korean Dictionary
                            Input: '{input_word}'
                            
                            Task:
                            1. Identify the correct word/phrase (fix typos).
                            2. Select 3 distinct meanings.
                            3. **CRITICAL:** If the word has multiple Parts of Speech (e.g., Noun AND Verb), YOU MUST INCLUDE BOTH TYPES.
                            4. Prefix the Korean meaning with the Part of Speech tag: [명사], [동사], [형용사] etc.
                            
                            STRICT Output Format:
                            CORRECT_WORD: <Corrected Word>
                            [POS] Korean Meaning @@@ English Example Sentence
                            """
                            response = model.generate_content(prompt)
                            st.session_state['analyzed_result'] = response.text
                            st.session_state['analyzed_word'] = input_word 
                        except Exception as e:
                            st.error(f"오류 발생: {e}")

    # 분석 결과 확인
    if 'analyzed_result' in st.session_state and 'analyzed_word' in st.session_state:
        raw_text = st.session_state['analyzed_result']
        
        meanings_list = []
        examples_list = []
        final_word = st.session_state.get('analyzed_word', 'Unknown')
        
        lines = raw_text.strip().split('\n')
        valid_data_lines = []
        
        for line in lines:
            line = line.strip()
            if not line: continue
            
            if line.startswith("CORRECT_WORD:"):
                try:
                    final_word = line.split(":", 1)[1].strip()
                    st.session_state['analyzed_word'] = final_word
                except:
                    pass
            elif "@@@" in line:
                valid_data_lines.append(line)

        for i, line in enumerate(valid_data_lines):
            parts = line.split("@@@", 1)
            raw_meaning = re.sub(r'^[\d\.\-\)\s]+', '', parts[0].strip())
            raw_example = re.sub(r'^[\d\.\-\)\s]+', '', parts[1].strip())
            
            meanings_list.append(f"{i+1}. {raw_meaning}")
            examples_list.append(f"{i+1}. {raw_example}")
        
        default_meaning = '\n'.join(meanings_list)
        default_example = '\n'.join(examples_list)

        if final_word in existing_words:
            st.warning(f"⚠️ '{final_word}'는 이미 단어장에 있습니다!")
        else:
            st.info(f"🧐 **{final_word}** (으)로 검색된 결과입니다.")
        
        with st.container():
            col1, col2 = st.columns(2)
            with col1:
                final_meaning = st.text_area("🇰🇷 뜻 (품사 포함)", value=default_meaning, height=150)
            with col2:
                final_example = st.text_area("🇺🇸 예문", value=default_example, height=150)

            if st.button("💾 단어장에 추가하기", type="primary", use_container_width=True):
                if not final_meaning or not final_example:
                    st.warning("내용이 비어있습니다.")
                elif final_word in existing_words:
                    st.error("이미 저장된 단어입니다.")
                else:
                    try:
                        current_df = conn.read(worksheet="Sheet1", usecols=[0, 1, 2], ttl=0)
                        new_entry = pd.DataFrame([{
                            "단어": final_word,
                            "뜻": final_meaning,
                            "예문": final_example
                        }])
                        updated_data = pd.concat([current_df, new_entry], ignore_index=True)
                        conn.update(worksheet="Sheet1", data=updated_data)
                        
                        st.toast(f"'{final_word}' 저장 성공! 🎉")
                        if 'analyzed_word' in st.session_state: del st.session_state['analyzed_word']
                        if 'analyzed_result' in st.session_state: del st.session_state['analyzed_result']
                        st.rerun()
                    except Exception as e:
                        st.error(f"저장 실패: {e}")

    # 목록 및 백업/링크 (여기가 수정되었습니다! ⭐)
    st.divider()
    
    # 버튼 공간을 좀 더 넉넉하게 잡음 (2:1)
    col_header, col_buttons = st.columns([2, 1])
    
    with col_header:
        st.subheader(f"📝 저장된 단어장 ({len(existing_data)}개)")
        filter_keyword = st.text_input("📂 내 단어장에서 찾기", placeholder="단어 철자나 뜻으로 검색해보세요...")

    with col_buttons:
        st.write("") # 줄 맞춤용
        st.write("")
        
        # 버튼 두 개를 나란히 배치하기 위해 작은 컬럼 생성
        b_col1, b_col2 = st.columns(2)
        
        with b_col1:
            # 1. 엑셀 백업 버튼
            if not existing_data.empty:
                csv = existing_data.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="💾 엑셀 백업",
                    data=csv,
                    file_name='my_voca_backup.csv',
                    mime='text/csv',
                    type='secondary',
                    use_container_width=True
                )
            else:
                st.write("") # 데이터 없으면 공란

        with b_col2:
            # 2. 구글 시트 바로가기 버튼 (자동 연결)
            # secrets에서 주소를 안전하게 가져옵니다.
            try:
                sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
            except:
                sheet_url = "https://docs.google.com/spreadsheets" # 혹시 실패하면 기본 주소
            
            st.link_button("📂 시트 열기", sheet_url, use_container_width=True)

    if not existing_data.empty:
        if filter_keyword:
            display_data = existing_data[
                existing_data['단어'].str.contains(filter_keyword, case=False, na=False) | 
                existing_data['뜻'].str.contains(filter_keyword, case=False, na=False)
            ]
        else:
            display_data = existing_data

        if display_data.empty:
            st.info("검색 결과가 없습니다.")
        else:
            for i in sorted(display_data.index, reverse=True):
                row = display_data.loc[i]
                with st.expander(f"📖 {row['단어']}"):
                    st.caption("👇 오른쪽 아이콘을 누르면 복사됩니다.")
                    st.code(row['단어'], language="text")
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        new_meaning = st.text_area("뜻", row['뜻'], key=f"m_{i}", height=100)
                    with c2:
                        new_example = st.text_area("예문", row['예문'], key=f"e_{i}", height=100)
                    
                    col_save, col_del = st.columns([1, 1])
                    with col_save:
                        if st.button("💾 수정", key=f"save_{i}"):
                            existing_data.at[i, "뜻"] = new_meaning
                            existing_data.at[i, "예문"] = new_example
                            conn.update(worksheet="Sheet1", data=existing_data)
                            st.toast("수정 완료!")
                            st.rerun()
                    with col_del:
                        if st.button("🗑️ 삭제", key=f"del_{i}"):
                            updated_data = existing_data.drop(index=i)
                            conn.update(worksheet="Sheet1", data=updated_data)
                            st.toast("삭제 완료!")
                            st.rerun()
    else:
        st.info("단어를 검색해서 추가해보세요!")

# ==========================================
# 탭 2: 영어 공부 도구함
# ==========================================
with tab2:
    st.header("🧰 유용한 영어 도구 모음")
    st.write("단어장과 함께 쓰면 좋은 사이트들을 모았습니다. 버튼만 누르세요!")
    
    st.divider()

    col_t1, col_t2 = st.columns(2)

    with col_t1:
        st.subheader("🤖 AI & 번역")
        st.link_button("🚀 Google Gemini (AI 비서)", "https://gemini.google.com", type="primary", use_container_width=True)
        st.link_button("🧠 DeepL (자연스러운 번역)", "https://www.deepl.com/translator", use_container_width=True)

    with col_t2:
        st.subheader("📚 사전 & 학습")
        st.link_button("🦜 Papago (네이버 번역)", "https://papago.naver.com", use_container_width=True)
        st.link_button("📘 Naver 영어사전", "https://en.dict.naver.com", use_container_width=True)
    
    st.info("💡 Tip: 'DeepL'은 뉘앙스를 살린 번역에, 'Papago'는 한국어 존댓말/반말 구분에 강합니다!")
