import json, logging, time, tempfile, os

import streamlit as st

from datetime import datetime
from typing import Dict, Any

from config_manager import config
from stt_tts import transcribe_audio_bytes, synthesize_tts
from html_generator import save_html_report
from ai_interviewer import AIInterviewer

# Configure logging
logger = logging.getLogger("streamlit_app")
logger.setLevel(getattr(logging, config.get("logging.level", "DEBUG")))
handler = logging.FileHandler(config.get("logging.file", "interview_debug.log"))
handler.setFormatter(logging.Formatter(config.get("logging.format", "%(asctime)s [%(levelname)s] %(message)s")))
if not logger.handlers:
    logger.addHandler(handler)

def load_interview_config() -> Dict[str, Any]:
    """Load interview configuration from JSON file."""
    config_path = "configs/interview_config.json"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Interview config file not found: {config_path}")
        # Return default config
        raise RuntimeError("Interview configuration file is missing.")
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in interview config: {e}")
        raise RuntimeError("Interview configuration file is invalid.")

def initialize_session_state():
    """Initialize Streamlit session state variables."""
    if 'interview_started' not in st.session_state:
        st.session_state.interview_started = False
    if 'interview_completed' not in st.session_state:
        st.session_state.interview_completed = False
    if 'current_question' not in st.session_state:
        st.session_state.current_question = ""
    if 'current_audio' not in st.session_state:
        st.session_state.current_audio = None
    if 'transcript' not in st.session_state:
        st.session_state.transcript = []
    if 'question_count' not in st.session_state:
        st.session_state.question_count = 0
    if 'ai_interviewer' not in st.session_state:
        st.session_state.ai_interviewer = None
    if 'interview_config' not in st.session_state:
        st.session_state.interview_config = load_interview_config()
    if 'audio_cache' not in st.session_state:
        st.session_state.audio_cache = {}

def save_audio_to_cache(text: str, audio_bytes: bytes) -> str:
    """Save audio to temporary file and cache the path."""
    if text in st.session_state.audio_cache:
        return st.session_state.audio_cache[text]
    
    # Create temporary file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
    temp_file.write(audio_bytes)
    temp_file.close()
    
    st.session_state.audio_cache[text] = temp_file.name
    logger.debug(f"Cached audio for text: {text[:50]}... at {temp_file.name}")
    return temp_file.name

def cleanup_audio_cache():
    """Clean up temporary audio files."""
    for text, file_path in st.session_state.audio_cache.items():
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
                logger.debug(f"Cleaned up audio file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup audio file {file_path}: {e}")
    st.session_state.audio_cache.clear()

def start_interview():
    """Start the interview process."""
    logger.info("Starting interview")
    st.session_state.interview_started = True
    st.session_state.ai_interviewer = AIInterviewer(st.session_state.interview_config)
    
    # Get introduction
    introduction = st.session_state.ai_interviewer.get_introduction()
    st.session_state.current_question = introduction
    
    # Generate TTS for introduction
    audio_bytes = synthesize_tts(introduction)
    if audio_bytes:
        st.session_state.current_audio = save_audio_to_cache(introduction, audio_bytes)
    
    # Add to transcript
    st.session_state.transcript.append({
        'type': 'greeting',
        'content': introduction,
        'timestamp': datetime.now().isoformat()
    })

def get_next_question():
    """Get the next question from AI interviewer."""
    if st.session_state.ai_interviewer:
        question = st.session_state.ai_interviewer.get_next_question()
        if question:
            st.session_state.current_question = question
            st.session_state.question_count += 1
            
            # Generate TTS for question
            audio_bytes = synthesize_tts(question)
            if audio_bytes:
                st.session_state.current_audio = save_audio_to_cache(question, audio_bytes)
            
            # Add to transcript
            st.session_state.transcript.append({
                'type': 'question',
                'content': question,
                'timestamp': datetime.now().isoformat()
            })
        else:
            # Interview completed
            complete_interview()

def rephrase_question():
    """Ask AI to rephrase the current question."""
    if st.session_state.ai_interviewer and st.session_state.current_question:
        rephrased = st.session_state.ai_interviewer.rephrase_question(st.session_state.current_question)
        if rephrased:
            st.session_state.current_question = rephrased
            
            # Generate new TTS
            audio_bytes = synthesize_tts(rephrased)
            if audio_bytes:
                st.session_state.current_audio = save_audio_to_cache(rephrased, audio_bytes)
            
            # Update transcript
            if st.session_state.transcript and st.session_state.transcript[-1]['type'] == 'question':
                st.session_state.transcript[-1]['content'] = rephrased
                st.session_state.transcript[-1]['timestamp'] = datetime.now().isoformat()

def process_answer(audio_data: bytes):
    """Process user's audio answer."""
    if not audio_data:
        st.warning("No audio data received")
        return
    
    logger.info(f"Processing audio answer: {len(audio_data)} bytes")
    
    # Transcribe audio
    with st.spinner("Transcribing your answer..."):
        transcript = transcribe_audio_bytes(audio_data)
    
    if transcript and not transcript.startswith("[STT_ERROR]"):
        # Add answer to transcript
        st.session_state.transcript.append({
            'type': 'answer',
            'content': transcript,
            'timestamp': datetime.now().isoformat()
        })
        
        # Send to AI interviewer
        if st.session_state.ai_interviewer:
            st.session_state.ai_interviewer.process_answer(transcript)
        
        # Clean up current audio cache for the answered question
        if st.session_state.current_question in st.session_state.audio_cache:
            file_path = st.session_state.audio_cache.pop(st.session_state.current_question)
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
                    logger.debug(f"Cleaned up answered question audio: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup answered question audio: {e}")
        
        # Get next question
        get_next_question()
        
        st.success("Answer recorded successfully!")
        st.rerun()
    else:
        st.error(f"Failed to transcribe audio: {transcript}")

def complete_interview():
    """Complete the interview and generate summary."""
    logger.info("Completing interview")
    st.session_state.interview_completed = True
    
    if st.session_state.ai_interviewer:
        # Generate interview summary
        with st.spinner("Generating interview summary..."):
            summary = st.session_state.ai_interviewer.generate_summary()
        
        # Prepare interview data for report
        interview_data = {
            'job_position': f"Position: {st.session_state.interview_config.get('position', 'Unknown')} at {st.session_state.interview_config.get('company', 'Unknown Company')}",
            'interview_summary': summary,
            'transcript': st.session_state.transcript,
            'timestamp': time.time(),
            'interview_config': st.session_state.interview_config  # Include full config for detailed job info
        }
        
        # Save interview data to session state for report generation
        st.session_state.interview_data = interview_data
    
    # Clean up all audio cache
    cleanup_audio_cache()

def main():
    """Main Streamlit application."""
    st.set_page_config(
        page_title="AI Interview Assistant",
        page_icon="",
        layout="wide"
    )
    
    # Hide only recorded audio elements, allow TTS playback
    st.markdown("""
    <style>
    /* Hide recorded audio playback specifically */
    .recorded-audio .stAudio {
        display: none !important;
    }
    /* Style for TTS audio controls */
    .tts-audio .stAudio {
        margin: 10px 0;
        border-radius: 8px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Load custom CSS
    try:
        with open("html/css/style.css", "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        logger.warning("Custom CSS file not found")
    
    initialize_session_state()
    
    # Header
    st.markdown('<h1 class="main-header">AI Interview Assistant</h1>', unsafe_allow_html=True)
    
    if not st.session_state.interview_started:
        # Pre-interview setup
        st.markdown('<div class="interview-card">', unsafe_allow_html=True)
        st.markdown("### Welcome to Your AI Interview")
        
        config_data = st.session_state.interview_config
        st.write(f"**Position:** {config_data.get('position', 'Not specified')}")
        st.write(f"**Company:** {config_data.get('company', 'Not specified')}")
        st.write(f"**Expected Duration:** {config_data.get('interview_duration', 15)} minutes")
        st.write(f"**Number of Questions:** {config_data.get('question_count', 5)}")
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.info("Click 'Start Interview' when you're ready to begin. Make sure your microphone is working properly.")
        
        if st.button("Start Interview", type="primary"):
            start_interview()
            st.rerun()
    
    elif not st.session_state.interview_completed:
        # Interview in progress
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Current question display
            if st.session_state.current_question:
                st.markdown('<div class="question-box">', unsafe_allow_html=True)
                st.markdown("### Current Question")
                st.write(st.session_state.current_question)
                st.markdown("</div>", unsafe_allow_html=True)
                
                # Audio controls
                col_repeat, col_rephrase = st.columns(2)
                
                with col_repeat:
                    if st.button("Repeat Question"):
                        if st.session_state.current_audio and os.path.exists(st.session_state.current_audio):
                            # Force audio replay by resetting the last_audio_played tracking
                            st.session_state.last_audio_played = None
                            st.success("Playing question again...")
                            st.rerun()
                
                with col_rephrase:
                    if st.button("Rephrase Question"):
                        with st.spinner("Rephrasing question..."):
                            rephrase_question()
                        st.rerun()
                
                # TTS Audio playback for questions
                if st.session_state.current_audio and os.path.exists(st.session_state.current_audio):
                    # Check if we just started or got a new question
                    if 'last_audio_played' not in st.session_state or st.session_state.last_audio_played != st.session_state.current_audio:
                        st.markdown('<div class="tts-audio">', unsafe_allow_html=True)
                        st.audio(st.session_state.current_audio, autoplay=True)
                        st.markdown("</div>", unsafe_allow_html=True)
                        st.session_state.last_audio_played = st.session_state.current_audio
        
        with col2:
            # Recording interface
            st.markdown("### Record Your Answer")
            
            # Import audio recorder
            try:
                from audiorecorder import audiorecorder
                
                wav_audio_data = audiorecorder("Click to record", "Click to stop recording")
                
                if wav_audio_data is not None and len(wav_audio_data) > 0:
                    st.success("Audio recorded successfully!")
                    # Hide recorded audio playback
                    st.markdown('<div class="recorded-audio" style="display: none;">', unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)
                    if st.button("Submit Answer", type="primary"):
                        # Convert AudioSegment to bytes
                        import io
                        buffer = io.BytesIO()
                        wav_audio_data.export(buffer, format="wav")
                        audio_bytes = buffer.getvalue()
                        process_answer(audio_bytes)
                        
            except ImportError:
                st.error("Audio recorder not available. Please install streamlit-audiorecorder")
                
                # Fallback file upload
                uploaded_audio = st.file_uploader("Upload your audio answer", type=['wav', 'mp3'])
                if uploaded_audio is not None:
                    if st.button("Submit Answer", type="primary"):
                        audio_bytes = uploaded_audio.read()
                        process_answer(audio_bytes)
        
        # Progress indicator
        progress = st.session_state.question_count / st.session_state.interview_config.get('question_count', 5)
        st.progress(progress)
        st.write(f"Question {st.session_state.question_count} of {st.session_state.interview_config.get('question_count', 5)}")
        
        # Transcript display
        if st.session_state.transcript:
            with st.expander("Interview Transcript", expanded=False):
                for entry in st.session_state.transcript:
                    if entry['type'] == 'greeting':
                        st.markdown('<div class="greeting">', unsafe_allow_html=True)
                        st.markdown("**AI Introduction:**")
                        st.write(entry['content'])
                        st.markdown("</div>", unsafe_allow_html=True)
                    elif entry['type'] == 'question':
                        st.markdown('<div class="question-box">', unsafe_allow_html=True)
                        st.markdown("**Question:**")
                        st.write(entry['content'])
                        st.markdown("</div>", unsafe_allow_html=True)
                    elif entry['type'] == 'answer':
                        st.markdown('<div class="answer-box">', unsafe_allow_html=True)
                        st.markdown("**Your Answer:**")
                        st.write(entry['content'])
                        st.markdown("</div>", unsafe_allow_html=True)
    
    else:
        # Interview completed
        st.success("Interview Completed!")
        
        st.markdown("### Interview Summary")
        if hasattr(st.session_state, 'interview_data'):
            summary = st.session_state.interview_data.get('interview_summary', 'Summary not available')
            st.write(summary)
            
            # Generate HTML report
            if st.button("Generate Detailed Report", type="primary"):
                with st.spinner("Generating detailed report..."):
                    report_path = save_html_report(st.session_state.interview_data)
                
                if report_path and os.path.exists(report_path):
                    st.success(f"Report generated: {report_path}")
                    
                    # Provide download link
                    with open(report_path, 'r', encoding='utf-8') as f:
                        report_content = f.read()
                    
                    st.download_button(
                        label="Download Report",
                        data=report_content,
                        file_name=f"interview_report_{int(time.time())}.html",
                        mime="text/html"
                    )
                else:
                    st.error("Failed to generate report")
        
        # Option to start new interview
        if st.button("Start New Interview"):
            # Reset session state
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

if __name__ == "__main__":
    main()