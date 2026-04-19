import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import google.generativeai as genai
import re
import random

# 1. 페이지 설정
st.set_page_config(page_title="방송대 영단어장", page_icon="🎓", layout="wide")
st.title("🎓 AI 영단어장 (V11: 퀴즈 모드 추가)")

# 2. Gemini 설정
try:
    if "gemini" in st.secrets and "api_key" in st.secrets["gemini"]:
        genai.configure(api_key=st.secrets["gemini"]["api_key"])
        model = genai.GenerativeModel('gemini-2.5-flash-lite')
    else:
        st.error("🚨 Secrets에 API 키가 없습니다.")
        model = None
except Exception as e:
    st.error(f"Gemini 설정 오류: {e}")
    model = None

# 3. 구글 시트 연결
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    existing_data = conn.read(worksheet="Sheet1", ttl=0)
    existing_data = existing_data.dropna(how="all")
    
    for col in ["단어", "뜻", "예문", "과목"]:
        if col not in existing_data.columns:
            existing_data[col] = "공통/기타" if col == "과목" else ""
            
    if not existing_data.empty:
        existing_words = existing_data["단어"].astype(str).str.strip().tolist()
    else:
        existing_words = []
except:
    existing_data = pd.DataFrame(columns=["단어", "뜻", "예문", "과목"])
    existing_words = []

# 전공 과목 리스트 
SUBJECTS = [
    "공통/기타",
    "영문법의 기초", 
    "영문법의 활용", 
    "영어교수법", 
    "테스트영어연습", 
    "영어회화1", 
    "영화로 생각하기", 
    "영작문2"
]

# 탭 구성
tab1, tab2, tab3 = st.tabs(["📚 단어장 관리", "🧰 영어 공부 도구함", "🎯 퀴즈 모드"])

# ==========================================
# 탭 1: 단어장
# ==========================================
with tab1:
    with st.expander("🔍 단어/숙어 분석 및 추가", expanded=True):
        with st.form("search_form", clear_on_submit=True):
            col_input, col_btn = st.columns([4, 1])
            with col_input:
                word_input = st.text_input("단어 또는 숙어 입력", placeholder="예: address")
            with col_btn:
                search_submitted = st.form_submit_button("🔍 분석")

            if search_submitted and word_input:
                input_word = word_input.strip()
                
                if not model:
                    st.error("AI 모델 연결 실패")
                else:
                    with st.spinner(f"AI가 '{input_word}'를 분석 중..."):
                        try:
                            prompt = f"""
                            Role: Comprehensive English-Korean Dictionary
                            Input: '{input_word}'
                            
                            Task:
                            1. Identify the correct word/phrase (fix typos).
                            2. Select 3 distinct meanings.
                            3. **CRITICAL:** If the word has multiple Parts of Speech (e.g., Noun AND Verb), YOU MUST INCLUDE BOTH TYPES.
                            4. Prefix the Korean meaning with the Part of Speech tag: [명사], [동사] etc.
                            
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
            st.info(f"🧐 **{final_word}** 검색 결과입니다.")
        
        with st.container():
            selected_subject_to_save = st.selectbox("📚 저장할 과목을 선택하세요", SUBJECTS)
            
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
                        current_df = conn.read(worksheet="Sheet1", ttl=0)
                        
                        for col in ["단어", "뜻", "예문", "과목"]:
                            if col not in current_df.columns:
                                current_df[col] = "공통/기타" if col == "과목" else ""

                        new_entry = pd.DataFrame([{
                            "단어": final_word,
                            "뜻": final_meaning,
                            "예문": final_example,
                            "과목": selected_subject_to_save
                        }])
                        updated_data = pd.concat([current_df, new_entry], ignore_index=True)
                        conn.update(worksheet="Sheet1", data=updated_data)
                        
                        st.toast(f"'{final_word}' 저장 성공! 🎉")
                        if 'analyzed_word' in st.session_state: del st.session_state['analyzed_word']
                        if 'analyzed_result' in st.session_state: del st.session_state['analyzed_result']
                        st.rerun()
                    except Exception as e:
                        st.error(f"저장 실패: {e}")

    # 목록 및 백업/링크
    st.divider()
    
    col_header, col_buttons = st.columns([2, 1])
    
    with col_header:
        st.subheader(f"📝 저장된 단어장 ({len(existing_data)}개)")
        
        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            filter_keyword = st.text_input("📂 단어/뜻 검색", placeholder="검색어 입력...")
        with filter_col2:
            if not existing_data.empty and '과목' in existing_data.columns:
                available_subjects = ["전체 보기"] + sorted(list(existing_data['과목'].dropna().unique()))
            else:
                available_subjects = ["전체 보기"]
            filter_subject = st.selectbox("📚 과목별 보기", available_subjects)

    with col_buttons:
        st.write("")
        st.write("")
        b_col1, b_col2 = st.columns(2)
        with b_col1:
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
        with b_col2:
            try:
                sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
            except:
                sheet_url = "https://docs.google.com/spreadsheets"
            st.link_button("📂 시트 열기", sheet_url, use_container_width=True)

    if not existing_data.empty:
        display_data = existing_data.copy()
        
        if filter_keyword:
            display_data = display_data[
                display_data['단어'].str.contains(filter_keyword, case=False, na=False) | 
                display_data['뜻'].str.contains(filter_keyword, case=False, na=False)
            ]
            
        if filter_subject != "전체 보기":
            if '과목' in display_data.columns:
                display_data = display_data[display_data['과목'] == filter_subject]

        if display_data.empty:
            st.info("조건에 맞는 단어가 없습니다.")
        else:
            for i in sorted(display_data.index, reverse=True):
                row = display_data.loc[i]
                subj_tag = f" [{row['과목']}]" if '과목' in row and pd.notna(row['과목']) else ""
                
                with st.expander(f"📖 {row['단어']}{subj_tag}"):
                    
                    col_copy, col_dict = st.columns([1, 1])
                    
                    with col_copy:
                        st.caption("복사하기")
                        st.code(row['단어'], language="text")
                        
                    with col_dict:
                        st.caption("발음 듣기 (네이버 사전)")
                        dict_url = f"https://en.dict.naver.com/#/search?query={row['단어']}"
                        st.link_button(f"🔊 {row['단어']} 발음 듣기", dict_url, use_container_width=True)

                    c1, c2 = st.columns(2)
                    with c1:
                        new_meaning = st.text_area("뜻", row['뜻'], key=f"m_{i}", height=100)
                    with c2:
                        new_example = st.text_area("예문", row['예문'], key=f"e_{i}", height=100)
                    
                    current_subj_val = row['과목'] if '과목' in row and pd.notna(row['과목']) else "공통/기타"
                    new_subj = st.selectbox("과목 변경", SUBJECTS, index=SUBJECTS.index(current_subj_val) if current_subj_val in SUBJECTS else 0, key=f"s_{i}")

                    col_save, col_del = st.columns([1, 1])
                    with col_save:
                        if st.button("💾 수정", key=f"save_{i}"):
                            existing_data.at[i, "뜻"] = new_meaning
                            existing_data.at[i, "예문"] = new_example
                            existing_data.at[i, "과목"] = new_subj
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
        st.subheader("🤖 번역 & 문법")
        st.link_button("🚀 Google Gemini (AI 비서)", "https://gemini.google.com", type="primary", use_container_width=True)
        st.link_button("🧠 DeepL (자연스러운 번역)", "https://www.deepl.com/translator", use_container_width=True)
        st.link_button("🦜 Papago (네이버 번역)", "https://papago.naver.com", use_container_width=True)
        st.link_button("✍️ Grammarly (문법 검사기)", "https://app.grammarly.com/", use_container_width=True)

    with col_t2:
        st.subheader("📺 학습 & 암기")
        st.link_button("📺 YouGlish (실제 발음 검색)", "https://youglish.com", use_container_width=True)
        st.link_button("🔁 Anki (플래시카드 암기)", "https://apps.ankiweb.net/", use_container_width=True)
    
    st.info("💡 Tip: YouGlish에서 검색하시면 실제 유튜브 영상들 속에서 원어민들이 해당 단어를 발음하는 문장들을 모아볼 수 있습니다.")

# ==========================================
# 탭 3: 퀴즈 모드
# ==========================================
with tab3:

    # ---------- 헬퍼: 퀴즈 초기화 ----------
    def start_quiz(words_df, mode, count):
        """
        words_df : 필터링된 DataFrame
        mode     : "단어 → 뜻" or "뜻 → 단어"
        count    : 문제 수 (int)
        """
        sampled = words_df.sample(n=min(count, len(words_df))).reset_index(drop=True)
        st.session_state["qz_words"]   = sampled.to_dict("records")  # list of dicts
        st.session_state["qz_mode"]    = mode
        st.session_state["qz_index"]   = 0
        st.session_state["qz_correct"] = 0
        st.session_state["qz_wrong"]   = 0
        st.session_state["qz_revealed"]= False
        st.session_state["qz_active"]  = True
        st.session_state["qz_done"]    = False

    def reset_quiz():
        for k in ["qz_words","qz_mode","qz_index","qz_correct",
                  "qz_wrong","qz_revealed","qz_active","qz_done"]:
            if k in st.session_state:
                del st.session_state[k]

    # ---------- 단어 없을 때 ----------
    if existing_data.empty:
        st.info("저장된 단어가 없습니다. 탭1에서 단어를 추가하세요!")
        st.stop()

    # ---------- 퀴즈 미시작: 설정 화면 ----------
    if not st.session_state.get("qz_active", False):

        st.header("🎯 퀴즈 모드")
        st.write("저장된 단어장으로 플래시카드 퀴즈를 풀어보세요!")
        st.divider()

        c1, c2, c3 = st.columns(3)

        with c1:
            # 과목 필터
            quiz_subjects = ["전체"] + sorted(
                [s for s in existing_data["과목"].dropna().unique() if s]
            )
            quiz_subject = st.selectbox("📚 과목 선택", quiz_subjects)

        with c2:
            # 문제 수
            if quiz_subject == "전체":
                max_count = len(existing_data)
            else:
                max_count = len(existing_data[existing_data["과목"] == quiz_subject])

            quiz_count = st.number_input(
                f"📝 문제 수 (최대 {max_count}개)",
                min_value=1,
                max_value=max(1, max_count),
                value=min(10, max_count),
                step=1
            )

        with c3:
            # 퀴즈 방향
            quiz_mode = st.selectbox(
                "🔄 퀴즈 방향",
                ["단어 → 뜻", "뜻 → 단어"]
            )

        st.write("")

        if st.button("🚀 퀴즈 시작!", type="primary", use_container_width=True):
            if quiz_subject == "전체":
                filtered_df = existing_data.copy()
            else:
                filtered_df = existing_data[existing_data["과목"] == quiz_subject].copy()

            if filtered_df.empty:
                st.warning("선택한 과목에 단어가 없습니다.")
            else:
                start_quiz(filtered_df, quiz_mode, int(quiz_count))
                st.rerun()

    # ---------- 결과 화면 ----------
    elif st.session_state.get("qz_done", False):

        words   = st.session_state["qz_words"]
        correct = st.session_state["qz_correct"]
        wrong   = st.session_state["qz_wrong"]
        total   = len(words)
        pct     = int(correct / total * 100) if total > 0 else 0

        st.header("🏁 퀴즈 완료!")
        st.divider()

        m1, m2, m3 = st.columns(3)
        m1.metric("✅ 맞음", f"{correct}개")
        m2.metric("❌ 틀림", f"{wrong}개")
        m3.metric("📊 정답률", f"{pct}%")

        st.write("")

        if pct == 100:
            st.success("🎉 완벽해요! 모두 다 알고 있네요!")
        elif pct >= 70:
            st.info("👍 잘했어요! 조금만 더 복습하면 완벽!")
        else:
            st.warning("💪 더 복습이 필요해요. 한 번 더 도전해보세요!")

        st.divider()

        # 틀린 단어 모아보기
        wrong_indices = [
            i for i, r in enumerate(words)
            if r.get("_result") == "wrong"
        ]
        if wrong_indices:
            with st.expander(f"❌ 틀린 단어 모아보기 ({len(wrong_indices)}개)"):
                for idx in wrong_indices:
                    row = words[idx]
                    st.markdown(f"**{row['단어']}**")
                    st.caption(row["뜻"])
                    st.divider()

        col_r1, col_r2 = st.columns(2)
        with col_r1:
            if st.button("🔄 같은 설정으로 다시", use_container_width=True):
                # 같은 단어 목록으로 재시작
                mode = st.session_state["qz_mode"]
                df_retry = pd.DataFrame(words).drop(columns=["_result"], errors="ignore")
                start_quiz(df_retry, mode, len(words))
                st.rerun()
        with col_r2:
            if st.button("🏠 설정 화면으로", use_container_width=True, type="primary"):
                reset_quiz()
                st.rerun()

    # ---------- 퀴즈 진행 중 ----------
    else:
        words   = st.session_state["qz_words"]
        idx     = st.session_state["qz_index"]
        mode    = st.session_state["qz_mode"]
        total   = len(words)

        # 혹시 인덱스 초과 → 완료 처리
        if idx >= total:
            st.session_state["qz_done"] = True
            st.rerun()

        current = words[idx]

        # 진행 표시
        st.progress((idx) / total, text=f"진행: {idx}/{total}문제")

        col_correct, col_wrong, col_quit = st.columns([2, 2, 1])
        col_correct.metric("✅ 맞음", st.session_state["qz_correct"])
        col_wrong.metric("❌ 틀림", st.session_state["qz_wrong"])
        with col_quit:
            st.write("")
            if st.button("🚪 종료", use_container_width=True):
                reset_quiz()
                st.rerun()

        st.divider()

        # 문제 카드
        st.markdown(f"### 문제 {idx + 1} / {total}")

        if mode == "단어 → 뜻":
            question_label = "🔤 단어"
            question_value = current["단어"]
            answer_label   = "🇰🇷 뜻"
            answer_value   = current["뜻"]
        else:
            question_label = "🇰🇷 뜻"
            question_value = current["뜻"]
            answer_label   = "🔤 단어"
            answer_value   = current["단어"]

        # 문제 표시
        st.markdown(
            f"""
            <div style="
                background: #1e3a5f;
                border-radius: 16px;
                padding: 32px;
                text-align: center;
                margin: 16px 0;
            ">
                <p style="color:#aac8e4; font-size:14px; margin:0 0 8px 0;">{question_label}</p>
                <p style="color:#ffffff; font-size:32px; font-weight:700; margin:0; word-break:break-word;">
                    {question_value}
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

        # 정답 공개 전
        if not st.session_state["qz_revealed"]:
            if st.button("👁️ 정답 보기", use_container_width=True, type="primary"):
                st.session_state["qz_revealed"] = True
                st.rerun()

        # 정답 공개 후
        else:
            # 정답 카드
            st.markdown(
                f"""
                <div style="
                    background: #1a4a2e;
                    border-radius: 16px;
                    padding: 24px;
                    text-align: center;
                    margin: 8px 0 16px 0;
                ">
                    <p style="color:#7fd4a0; font-size:14px; margin:0 0 8px 0;">{answer_label}</p>
                    <p style="color:#d4f5e2; font-size:22px; font-weight:600; margin:0; word-break:break-word;">
                        {answer_value}
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )

            # 예문도 보여주기
            if current.get("예문"):
                with st.expander("📖 예문 보기"):
                    st.write(current["예문"])

            # 맞음/틀림 버튼
            btn_col1, btn_col2 = st.columns(2)

            with btn_col1:
                if st.button("✅ 알았어!", use_container_width=True, type="primary"):
                    st.session_state["qz_words"][idx]["_result"] = "correct"
                    st.session_state["qz_correct"] += 1
                    st.session_state["qz_index"]   += 1
                    st.session_state["qz_revealed"] = False
                    # 마지막 문제였으면 완료
                    if st.session_state["qz_index"] >= total:
                        st.session_state["qz_done"] = True
                    st.rerun()

            with btn_col2:
                if st.button("❌ 몰랐어...", use_container_width=True):
                    st.session_state["qz_words"][idx]["_result"] = "wrong"
                    st.session_state["qz_wrong"] += 1
                    st.session_state["qz_index"] += 1
                    st.session_state["qz_revealed"] = False
                    if st.session_state["qz_index"] >= total:
                        st.session_state["qz_done"] = True
                    st.rerun()
