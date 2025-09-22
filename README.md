# AI Interview Assistant
An intelligent interview system that conducts automated job interviews using AI, speech-to-text, and text-to-speech technologies. The system provides a complete interview experience from question generation to comprehensive evaluation reports.

## Table of Contents

- [AI Interview Assistant](#ai-interview-assistant)
  - [Table of Contents](#table-of-contents)
  - [Features](#features)
  - [Prerequisites](#prerequisites)
  - [Installation Steps](#installation-steps)
  - [Run the Application](#run-the-application)
  - [How It Works](#how-it-works)
  - [External Services](#external-services)
  - [Feature Details](#feature-details)
  - [Configuration Files](#configuration-files)
  - [Debug Features](#debug-features)
  - [Troubleshooting](#troubleshooting)
  - [Performance Optimization](#performance-optimization)
  - [License](#license)

## Features

**Voice-Enabled Interviews**
- Toggle-based audio recording and transcription using Google Cloud Speech-to-Text
- Natural-sounding AI interviewer voice using Google Cloud Text-to-Speech
- Support for multiple audio formats (WAV, MP3, raw PCM)

**AI-Powered Interviewing**
- Dynamic question generation using NVIDIA NIM ```meta/llama-4-maverick-17b-128e-instruct```
- Context-aware follow-up questions based on candidate responses
- Question rephrasing for clarity when requested
- Adaptive interview flow based on job requirements

**Comprehensive Evaluation**
- Automated candidate assessment with numerical scoring (1-10)
- Detailed analysis of technical skills, communication, and problem-solving abilities
- Identification of strengths and areas for improvement
- Professional recommendation (Hire/Don't Hire/Further Review)

**Professional Reporting**
- Beautiful HTML interview reports with professional styling
- Complete interview transcript with timestamps
- Downloadable reports for HR teams
- Mobile-responsive design for viewing on any device

**Configurable Interview Setup**
- Customizable interview parameters (duration, question count, focus areas)
- Job-specific configuration through JSON files
- Multiple evaluation criteria with weighted scoring
- Company and position-specific question generation

## Prerequisites
**System Requirements**
- Python 3.8+
- ffmpeg (for audio processing)
- Active internet connection (for API services)

**API Keys Required**
1. Google Cloud Platform Account
    - Speech-to-Text API enabled
    - Text-to-Speech API enabled
    - Service account JSON key file
2. NVIDIA NIM API Key
    - Access to Llama 4 Maverick 17b 128e Instruct

## Installation Steps

**1. Clone Repository**
```
git clone https://github.com/starbachi/LLM_Interview_Agent
```
**2.Run ```setup.sh```**
```
cd "LLM_Interview_Agent"
bash helpers/setup.sh
```
**3. Setup API credentials**
Inside ```helpers/api/api.env```, place your API keys.
Example:
NVIDIA_API_KEY=your_nvidia_api_key_here
GOOGLE_APPLICATION_CREDENTIALS=path/to/your/google-credentials.json
**4. Configure interview settings**
Edit ```configs/interview_config.json``` with your job requirements (find example template in the same directory):

## Run the Application
```
streamlit run streamlit_app.py
```
The application will be available at http://localhost:8501

## How It Works

**Architecture Overview**

The system follows a modular architecture with clear separation of concerns:

**1. Streamlit Frontend (```streamlit_app.py```)**
- Interview Management: Handles interview lifecycle (start, progress, completion)
- Audio Recording: Toggle-based audio capture using ```streamlit-audiorecorder``` library
- User Interface: Professional, responsive web interface
- Session Management: Maintains interview state and transcript
- Progress Tracking: Visual progress indicators and question counters

**2. AI Interviewer Engine (```ai_interviewer.py```)**
- Question Generation: Creates contextually relevant interview questions
- Conversation Management: Maintains interview flow and context
- Response Analysis: Processes candidate answers for follow-up questions
- Evaluation Logic: Generates comprehensive candidate assessments
- API Integration: Manages communication with NVIDIA NIM ```meta/llama-4-maverick-17b-128e-instruct```

**3. Speech Processing (```stt_tts.py```)**
- Audio Normalization: Converts various audio formats to Google STT requirements
- Speech Recognition: Transcribes candidate responses using Google Cloud STT
- Voice Synthesis: Generates natural AI interviewer voice using Google TTS
- Error Handling: Robust audio processing with fallback mechanisms
- Debug Support: Audio file logging for troubleshooting

**4. Configuration Manager (```config_manager.py```)**
- YAML Configuration: Loads settings from ```configs/config.yaml```
- Directory Management: Creates and manages debug audio directories
- API Settings: Manages STT/TTS service configurations
- Debug Controls: Configurable debug modes and file retention

**5. Report Generator (```html_generator.py```)**
- HTML Generation: Creates professional interview reports
- Template Processing: Uses ```frontend/interview_report_template.html```
- Data Extraction: Parses AI evaluation results for structured display
- Styling: Responsive CSS with professional formatting
- Export Functions: Generates downloadable reports

## External Services
**NVIDIA NIM (Neural Inference Microservices)**
- Model: Lama 4 Maverick 17b 128e Instruct
- Purpose: Question generation, conversation management, candidate evaluation
- Features: Advanced reasoning, context awareness, professional assessment
- API Endpoint: https://integrate.api.nvidia.com/v1/chat/completions

**Google Cloud Speech-to-Text**
- Features: Transcription generation, basic models
- Languages: Configurable (default: en-GB)
- Audio Support: Multiple formats with automatic normalization (WAV, PCM, LINEAR16)
- Configuration: Lowest-cost, most basic model

**Google Cloud Text-to-Speech**
- Voice: Most budget-friendly voice (default: en-GB-Standard-A)
- Output: MP3 audio for natural interviewer speech
- Integration: Playback in web interface
- Caching: Audio files cached for repeat playback

## Feature Details

**Interview Flow**
1. Setup Phase: Load job configuration and initialize AI interviewer
2. Introduction: AI provides welcoming introduction with interview overview
3. Question Loop: Dynamic question generation based on focus areas
4. Response Processing: Audio capture, transcription, and analysis
5. Completion: Comprehensive evaluation and report generation

**Audio Processing Pipeline**
1. Capture: Toogle-based audio recording in web browser
2. Format Detection: Automatic detection of WAV vs raw PCM
3. Normalization: Conversion to Google STT requirements (16kHz, mono, 16-bit)
4. Transcription: High-accuracy speech recognition with confidence scoring
5. Debug Logging: Optional audio file saving for troubleshooting

**Evaluation System**
1. Multi-dimensional Assessment: Technical skills, communication, problem-solving
2. Weighted Scoring: Configurable criteria weights in interview config
3. Context-Aware Analysis: AI considers job requirements and candidate responses
4. Professional Output: Structured recommendations suitable for HR decisions

## Debug Features
Audio Debug Mode
- Raw Input Files: Original recordings saved to ```debug_audio/raw_input```
- Normalized Audio: Processed files saved to ```debug_audio/normalized```
- Failed Processing: Problem files saved to ```debug_audio/failed_stt```
- Configurable Retention: Automatic cleanup with file limits

Logging
- Comprehensive Logging: All operations logged to ```interview_debug.log```
- Configurable Levels: DEBUG, INFO, WARNING, ERROR
- API Tracking: Request/response logging for troubleshooting
- Error Analysis: Detailed error messages with context

## Troubleshooting
**Common Issues**
- Audio Not Recording
    - Check microphone permissions in browser
    - Ensure ```streamlit-audiorecorder``` library is installed
    - Try file upload fallback option
- STT Not Working
    - Verify Google Cloud credentials are correctly set
    - Check ```GOOGLE_APPLICATION_CREDENTIALS``` path
    - Review audio debug files for format issues
- AI Questions Not Generating
    - Confirm NVIDIA API key is valid and active
    - Check internet connectivity
    - Review ```interview_debug.log``` for API errors
- Poor Audio Quality
    - Ensure quiet environment for recording
    - Check microphone settings and positioning
    - Review normalized audio files in debug directory (```debug_audio/normalized```)

## Performance Optimization
- Audio Caching: TTS responses cached to avoid repeated API calls
- Efficient Processing: Audio normalization optimized for Google STT
- Error Recovery: Graceful fallbacks for API failures
- Resource Management: Automatic cleanup of temporary files

## License
This project uses several external services and libraries. Ensure compliance with:

- Google Cloud Platform Terms of Service
- NVIDIA NIM API Terms of Use
- Streamlit License
- All dependency licenses listed in requirements.txt