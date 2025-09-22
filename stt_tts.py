import os, io, logging, wave

from typing import Optional
from dotenv import load_dotenv
from datetime import datetime
from google.cloud import speech, texttospeech
from pydub import AudioSegment

from config_manager import config

# ---------------------------------------------------------------------------- #
#                                    HELPERS                                   #
# ---------------------------------------------------------------------------- #

# Configure logger using config
logger = logging.getLogger("stt_tts")
logger.setLevel(getattr(logging, config.get("logging.level", "DEBUG")))
handler = logging.FileHandler(config.get("logging.file", "interview_debug.log"))
handler.setFormatter(logging.Formatter(config.get("logging.format", "%(asctime)s [%(levelname)s] %(message)s")))
if not logger.handlers:
    logger.addHandler(handler)

# Initialise debug directories on module load
debug_dirs = config.setup_debug_directories()
if debug_dirs:
    logger.info(f"Debug directories initialised: {list(debug_dirs.keys())}")


# ------------------------- RECOGNITIONCONFIG FACTORY ------------------------ #
def __create_recognition_config(sample_rate: int, channels: int, language_code: Optional[str] = None) -> speech.RecognitionConfig:
    """Create a standardized RecognitionConfig for Google STT."""
    if language_code is None:
        language_code = config.get("stt.google.language_code", "en-GB")
    
    return speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=sample_rate,
        language_code=language_code,
        audio_channel_count=channels,
        enable_automatic_punctuation=config.get("stt.google.enable_automatic_punctuation", True),
        use_enhanced=config.get("stt.google.enhanced", True),
        model=config.get("stt.google.model", "latest_long"),
        enable_spoken_punctuation=config.get("stt.google.enable_spoken_punctuation", True),
        enable_spoken_emojis=config.get("stt.google.enable_spoken_emojis", True),
        profanity_filter=config.get("stt.google.profanity_filter", False),
    )

# ------------------------ AUDIO NORMALIZATION HANDLER ----------------------- #
def __prepare_audio_for_api(audio_bytes: bytes) -> tuple[bytes, int, int]:
    """
    Prepare audio for Google STT API by normalizing to LINEAR16 PCM.
    
    Returns:
        tuple[bytes, int, int]: (linear16_pcm_bytes, sample_rate, channels)
    
    Raises:
        ValueError: If audio format cannot be processed
    """
    if not audio_bytes:
        logger.error("_prepare_audio_for_api called with empty audio_bytes")
        raise ValueError("Empty audio bytes provided")
    
    is_wav = len(audio_bytes) >= 4 and audio_bytes[:4] == b'RIFF'
    logger.debug(f"Audio input: {len(audio_bytes)} bytes, is_wav={is_wav}")
    

    # Detects WAV by RIFF header, extracts raw PCM from the container, checks if it's already 16kHz/mono/16-bit and not different like stereio 44.1 kHz.
    # If yes, returns the raw PCM immediately. If no, creates an AudioSegment for normalization.
    # If it does NOT detect WAV, assumes it's raw LINEAR16 PCM at 16kHz mono 16-bit and creates an AudioSegment.
    try:
        if is_wav:
            # Extract audio data from WAV wrapper
            with wave.open(io.BytesIO(audio_bytes), 'rb') as wf:
                original_rate = wf.getframerate()
                original_channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                frames = wf.readframes(wf.getnframes())
                logger.debug(f"WAV: {original_rate}Hz, {original_channels}ch, {sample_width*8}bit")
                
                # If already LINEAR16, 16kHz mono 16-bit, return as-is
                if original_rate == 16000 and original_channels == 1 and sample_width == 2:
                    return frames, 16000, 1
                
                # Otherwise normalize with pydub
                seg = AudioSegment(data=frames, sample_width=sample_width, 
                                 frame_rate=original_rate, channels=original_channels)
        else:
            # Assume raw LINEAR16 PCM at 16kHz mono
            logger.debug("Assuming raw LINEAR16 PCM: 16kHz, mono, 16-bit")
            seg = AudioSegment(data=audio_bytes, sample_width=2, 
                             frame_rate=16000, channels=1)
        
        # Normalize to Google STT requirements: 16kHz, mono, 16-bit
        normalized = seg.set_frame_rate(16000).set_channels(1).set_sample_width(2)
        
        # Export as raw LINEAR16 PCM
        out_buf = io.BytesIO()
        normalized.export(out_buf, format='raw')
        linear16_pcm = out_buf.getvalue()
        
        logger.debug(f"Normalized: {len(linear16_pcm)} bytes, {len(normalized)}ms duration")
        return linear16_pcm, 16000, 1
        
    except Exception as e:
        logger.exception("_prepare_audio_for_api has failed audio preparation")
        raise ValueError(f"Cannot process audio format: {e}")

# ------------------------------- API VERIFIER ------------------------------- #
def __get_google_credentials_json_path():
    """Load Google Cloud credentials from `api.env` file."""

    env_file_path = os.path.join(os.path.dirname(__file__), 'api', 'api.env')
    
    if env_file_path is None:
        logger.error("File containing Google Cloud credentials is missing.")
        raise RuntimeError(f"Failed to load {env_file_path} for Google credentials")
    else:
        load_dotenv(env_file_path)
        logger.debug(f"Loaded environment from {env_file_path}")
        credentials = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')

    if credentials:
        if not os.path.isabs(credentials):
            credentials = os.path.abspath(credentials)
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials

    return credentials

# ---------------------------- GOOGLE STT HANDLER ---------------------------- #
def __google_stt_from_bytes(audio_bytes: bytes, language_code: str = "en-GB") -> str:
    """Transcribe audio bytes using Google Cloud Speech-to-Text API.
    Args:
        audio_bytes (bytes): Raw audio bytes (WAV or raw PCM)
        language_code (str): Language code for transcription (default: "en-GB")
    Returns:
        str: Transcribed text
    Raises:
        RuntimeError: If Google credentials are not set
    """
    if not audio_bytes:
        logger.error("_google_stt_from_bytes called with empty audio_bytes")
        return ""
    
    # Ensure credentials are loaded and log which file is used
    cred = __get_google_credentials_json_path()
    if cred:
        logger.debug(f"Using GOOGLE_APPLICATION_CREDENTIALS: {cred}, exists={os.path.exists(cred)}")
    else:
        logger.error("GOOGLE_APPLICATION_CREDENTIALS not set")
        raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS not set")

    # Initialize the Google Speech client
    try:
        client = speech.SpeechClient()
    except Exception as e:
        logger.exception("Failed to create SpeechClient, please check credentials")
        raise

    try:
        # Prepare audio
        linear16_pcm, sample_rate, channels = __prepare_audio_for_api(audio_bytes)
        
        # Create audio and config objects
        audio = speech.RecognitionAudio(content=linear16_pcm)
        config = __create_recognition_config(sample_rate, channels, language_code)
        
        logger.debug(
            f"Calling SpeechClient.recognize with config: sample_rate={config.sample_rate_hertz} "
            f"channels={config.audio_channel_count} encoding={config.encoding}"
        )
        
        response = client.recognize(config=config, audio=audio)
        
        # Log response summary
        logger.debug(f"Google STT response: result_count={len(response.results)}")
        transcripts = []
        
        # When multiple results are returned, choose the one with highest confidence
        # and ignore low-confidence or empty transcripts
        for i, result in enumerate(response.results):
            logger.debug(f"result[{i}] has {len(result.alternatives)} alternatives")
            if result.alternatives:
                alt = result.alternatives[0]
                confidence = getattr(alt, 'confidence', 'n/a')
                transcript = getattr(alt, 'transcript', '')
                logger.debug(f"result[{i}].confidence={confidence}")
                logger.debug(f"result[{i}].transcript='{transcript}' (length={len(transcript)})")
                
                # Only include transcripts with confidence > 0 and non-empty content
                if confidence != 'n/a' and isinstance(confidence, (int, float)) and confidence >= 0.0 and transcript.strip():
                    transcripts.append(transcript)
                elif transcript.strip():  # Non-empty but low confidence
                    logger.warning(f"Low confidence transcript ignored: Confidence={confidence}, Text='{transcript}'")
                else:
                    logger.debug(f"Empty transcript ignored: Confidence={confidence}")
            else:
                logger.warning(f"Result[{i}] has no alternatives")

        joined = " ".join(transcripts)
        logger.info(f"Final joined transcript: '{joined}' (length={len(joined)})")
        
        # Ensure we don't return just whitespace
        if not joined.strip():
            logger.warning("Google STT returned only empty/whitespace transcript")
            # Save the exact audio data that was sent to Google STT for analysis
            if config:
                now = datetime.now().strftime('%Y%m%d_%H%M%S')
                try:
                    # Save the exact normalized PCM data that Google STT received
                    raw_file = config.get_debug_file_path("failed", f"normalized_audio_{now}", "raw")
                    if raw_file:
                        with open(raw_file, "wb") as f:
                            f.write(linear16_pcm)
                        logger.warning(f"Saved normalized audio sent to STT: {raw_file}")
                    
                    # Also create a WAV version for easier analysis
                    try:
                        wav_file = config.get_debug_file_path("failed", f"normalized_audio_{now}", "wav")
                        if wav_file:
                            with wave.open(wav_file, 'wb') as wf:
                                wf.setnchannels(channels)
                                wf.setsampwidth(2)  # 16-bit
                                wf.setframerate(sample_rate)
                                wf.writeframes(linear16_pcm)
                            logger.warning(f"Saved normalized audio as WAV: {wav_file}")
                    except Exception:
                        logger.exception("Failed to save normalized audio as WAV")
                except Exception:
                    logger.exception("Failed to save normalized audio for diagnosis")
            return ""
        
        return joined
        
    except ValueError as e:
        logger.error(f"Audio format error: {e}")
        return ""
    except Exception as e:
        logger.exception("Google STT recognize() failed")
        raise

# ------------------------- PUBLIC INTERFACE FOR STT ------------------------- #
def transcribe_audio_bytes(audio_bytes: bytes) -> str:
    """Transcribe audio bytes using configured STT service.
    Currently only Google Cloud Speech-to-Text is supported.
    Returns:
        str: Transcribed text or error message
    """
    if not audio_bytes:
        logger.warning("transcribe_audio_bytes called with empty audio_bytes")
        return ""
    
    if len(audio_bytes) < 44:  # Minimum WAV header size
        logger.warning(f"transcribe_audio_bytes called with suspiciously small audio_bytes: {len(audio_bytes)} bytes")
        return ""
    
    logger.info(f"transcribe_audio_bytes called with {len(audio_bytes)} bytes")
    
    try:
        # Google expects raw bytes of the audio file; for many WAV files this works.
        # Ensure credentials are available when calling
        __get_google_credentials_json_path()
        logger.debug("Credential JSON located, calling _google_stt_from_bytes")
        transcript = __google_stt_from_bytes(audio_bytes)
        logger.info(f"_google_stt_from_bytes returned: '{transcript}' (length={len(transcript) if transcript else 0})")
        
        if transcript:
            logger.info(f"STT succeeded, returning transcript of length={len(transcript)}")
            return transcript
        else:
            logger.warning("STT returned empty transcript; saving diagnostic files")
    except Exception as e:
        logger.exception("Google STT failed")
        # Return an informative message for the UI
        return f"[STT_ERROR] {e}"

    # Save diagnostics for inspection if debug is enabled
    if config:
        now = datetime.now().strftime('%Y%m%d_%H%M%S')
        try:
            # If bytes look like a WAV (RIFF), save as WAV, else save raw
            if len(audio_bytes) >= 4 and audio_bytes[:4] == b'RIFF':
                wav_file = config.get_debug_file_path("raw", f"recording_{now}", "wav")
                if wav_file:
                    with open(wav_file, "wb") as f:
                        f.write(audio_bytes)
                    logger.debug(f"Saved diagnostic WAV to {wav_file}")
            else:
                raw_file = config.get_debug_file_path("raw", f"recording_{now}", "raw")
                if raw_file:
                    with open(raw_file, "wb") as f:
                        f.write(audio_bytes)
                    logger.debug(f"Saved diagnostic RAW to {raw_file}")
        except Exception:
            logger.exception("Failed to save diagnostic audio files")

    return "[Transcript Placeholder]"

# ------------------------- PUBLIC INTERFACE FOR TTS ------------------------- #
def synthesize_tts(text: str, language_code: Optional[str] = None, voice_name: Optional[str] = None) -> Optional[bytes]:
    """Synthesize text to speech using Google Cloud Text-to-Speech.

    Returns raw audio bytes (WAV/MP3) suitable for Streamlit `st.audio`.
    """
    if not text:
        return None
    
    # Use config defaults if not provided
    if language_code is None: language_code = config.get("tts.google.language_code", "en-GB")
    if voice_name is None: voice_name = config.get("tts.google.voice_name", "en-GB-Standard-A")
        
    try:
        # Ensure credentials are loaded
        __get_google_credentials_json_path()
        
        # Initialize the client
        client = texttospeech.TextToSpeechClient()
        
        # Set the text input to be synthesized
        synthesis_input = texttospeech.SynthesisInput(text=text)
        
        # Build the voice request
        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=voice_name
        )
        
        # Select the type of audio file you want returned
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )
        
        # Perform the text-to-speech request
        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        
        logger.info(f"TTS synthesis successful for text length: {len(text)}")
        return response.audio_content
        
    except Exception as e:
        logger.exception(f"TTS synthesis failed: {e}")
        return None
