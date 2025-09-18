import json
import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

import requests
from config_manager import config

logger = logging.getLogger("ai_interviewer")
logger.setLevel(getattr(logging, config.get("logging.level", "DEBUG")))
handler = logging.FileHandler(config.get("logging.file", "interview_debug.log"))
handler.setFormatter(logging.Formatter(config.get("logging.format", "%(asctime)s [%(levelname)s] %(message)s")))
if not logger.handlers:
    logger.addHandler(handler)

class AIInterviewer:
    """AI-powered interviewer using NVIDIA NIM Qwen3 80B model."""
    
    def __init__(self, interview_config: Dict[str, Any]):
        """
        Initialize the AI interviewer.
        
        Args:
            interview_config: Configuration for the interview
        """
        self.config = interview_config
        self.conversation_history: List[Dict[str, str]] = []
        self.questions_asked = 0
        self.max_questions = interview_config.get('question_count', 5)
        self.focus_areas = interview_config.get('focus_areas', ['technical_skills', 'communication'])
        self.user_responses: List[str] = []
        
        # Load NVIDIA API configuration
        self.api_key = self._load_nvidia_api_key()
        self.base_url = "https://integrate.api.nvidia.com/v1"
        
        logger.info(f"AI Interviewer initialized for position: {self.config.get('position', 'Unknown')}")
    
    def _load_nvidia_api_key(self) -> str:
        """Load NVIDIA API key from environment file."""
        import os
        from dotenv import load_dotenv
        
        env_file_path = os.path.join(os.path.dirname(__file__), 'api', 'api.env')
        if os.path.exists(env_file_path):
            load_dotenv(env_file_path)
            api_key = os.getenv('NVIDIA_API_KEY')
            if api_key:
                logger.debug("NVIDIA API key loaded successfully")
                return api_key
        
        logger.error("NVIDIA API key not found")
        raise RuntimeError("NVIDIA_API_KEY not set in api/api.env")
    
    def _call_nvidia_api(self, messages: List[Dict[str, str]], max_tokens: int = 1000) -> Optional[str]:
        """
        Call NVIDIA NIM API with the given messages.
        
        Args:
            messages: List of conversation messages
            max_tokens: Maximum tokens in response
            
        Returns:
            AI response text or None if failed
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "meta/llama-3.1-405b-instruct",
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7,
            "top_p": 0.9,
            "stream": False
        }
        
        try:
            logger.debug(f"Calling NVIDIA API with {len(messages)} messages")
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0:
                content = result['choices'][0]['message']['content']
                logger.debug(f"NVIDIA API response received: {len(content)} characters")
                return content
            else:
                logger.error("Invalid response format from NVIDIA API")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"NVIDIA API request failed: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse NVIDIA API response: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error calling NVIDIA API: {e}")
            return None
    
    def get_introduction(self) -> str:
        """Generate the interview introduction."""
        system_prompt = f"""You are an AI interviewer conducting a professional job interview. 

Job Details:
- Position: {self.config.get('position', 'Not specified')}
- Company: {self.config.get('company', 'Not specified')}
- Required Skills: {', '.join(self.config.get('required_skills', []))}
- Focus Areas: {', '.join(self.focus_areas)}

Generate a brief, professional introduction (2-3 sentences maximum) that:
1. Introduces yourself as the AI interviewer
2. Briefly explains the interview structure and purpose
3. Sounds natural and welcoming

Keep it concise and professional."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Please provide the interview introduction."}
        ]
        
        introduction = self._call_nvidia_api(messages, max_tokens=200)
        
        if introduction:
            self.conversation_history.append({
                "role": "assistant", 
                "content": introduction,
                "type": "introduction"
            })
            return introduction
        else:
            # Fallback introduction
            fallback = f"Hello! I'm your AI interviewer for the {self.config.get('position', 'position')} role at {self.config.get('company', 'our company')}. I'll be asking you {self.max_questions} questions to assess your qualifications and fit for this role. Let's begin!"
            logger.warning("Using fallback introduction due to API failure")
            return fallback
    
    def get_next_question(self) -> Optional[str]:
        """Generate the next interview question."""
        if self.questions_asked >= self.max_questions:
            logger.info("Maximum questions reached, ending interview")
            return None
        
        # Determine focus area for this question
        focus_index = self.questions_asked % len(self.focus_areas)
        current_focus = self.focus_areas[focus_index]
        
        system_prompt = f"""You are conducting a professional job interview for the following position:

Job Details:
- Position: {self.config.get('position', 'Not specified')}
- Company: {self.config.get('company', 'Not specified')}
- Job Description: {self.config.get('job_description', 'Not provided')}
- Required Skills: {', '.join(self.config.get('required_skills', []))}

Current Question Focus: {current_focus}
Question Number: {self.questions_asked + 1} of {self.max_questions}

Previous conversation context:
{self._get_conversation_context()}

Generate a single, clear, and relevant interview question that:
1. Focuses on the current area: {current_focus}
2. Is appropriate for the job level and requirements
3. Encourages detailed responses
4. Sounds natural and conversational
5. Is different from previously asked questions

Provide ONLY the question, no additional text or formatting."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Generate the next interview question."}
        ]
        
        question = self._call_nvidia_api(messages, max_tokens=300)
        
        if question:
            question = question.strip()
            self.conversation_history.append({
                "role": "assistant",
                "content": question,
                "type": "question",
                "focus_area": current_focus
            })
            self.questions_asked += 1
            logger.info(f"Generated question {self.questions_asked}: {question[:50]}...")
            return question
        else:
            # Fallback question based on focus area
            fallback_questions = {
                'technical_skills': f"Can you describe your experience with {', '.join(self.config.get('required_skills', ['the required technologies'])[:2])}?",
                'problem_solving': "Can you walk me through how you approach solving complex technical problems?",
                'communication': "How do you ensure effective communication when working with team members from different technical backgrounds?",
                'experience': "Tell me about a challenging project you've worked on and how you overcame the difficulties.",
                'motivation': f"What interests you most about this {self.config.get('position', 'position')} role?"
            }
            
            fallback = fallback_questions.get(current_focus, "Can you tell me more about your background and experience?")
            logger.warning(f"Using fallback question for {current_focus}")
            return fallback
    
    def process_answer(self, answer: str) -> None:
        """
        Process the user's answer and store it.
        
        Args:
            answer: User's response to the current question
        """
        if answer and answer.strip():
            self.conversation_history.append({
                "role": "user",
                "content": answer.strip(),
                "type": "answer"
            })
            self.user_responses.append(answer.strip())
            logger.info(f"Processed user answer: {len(answer)} characters")
        else:
            logger.warning("Empty or invalid answer received")
    
    def rephrase_question(self, original_question: str) -> Optional[str]:
        """
        Rephrase the current question to make it simpler or clearer.
        
        Args:
            original_question: The original question to rephrase
            
        Returns:
            Rephrased question or None if failed
        """
        system_prompt = f"""You are an AI interviewer. The candidate has asked you to rephrase the current question.

Original question: "{original_question}"

Job context:
- Position: {self.config.get('position', 'Not specified')}
- Required Skills: {', '.join(self.config.get('required_skills', []))}

Please rephrase this question to be:
1. Simpler and clearer
2. More conversational
3. Easier to understand
4. Focused on the same core topic

Provide ONLY the rephrased question, no additional text."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Please rephrase the question."}
        ]
        
        rephrased = self._call_nvidia_api(messages, max_tokens=200)
        
        if rephrased:
            rephrased = rephrased.strip()
            logger.info(f"Rephrased question: {rephrased[:50]}...")
            return rephrased
        else:
            logger.warning("Failed to rephrase question, returning original")
            return original_question
    
    def generate_summary(self) -> str:
        """Generate a comprehensive interview summary and evaluation."""
        if not self.user_responses:
            logger.warning("No user responses to summarize")
            return "No responses were recorded during the interview."
        
        system_prompt = f"""You are an expert HR interviewer analyzing an interview. Provide a comprehensive evaluation based on the following:

Job Details:
- Position: {self.config.get('position', 'Not specified')}
- Company: {self.config.get('company', 'Not specified')}
- Job Description: {self.config.get('job_description', 'Not provided')}
- Required Skills: {', '.join(self.config.get('required_skills', []))}
- Focus Areas: {', '.join(self.focus_areas)}

Interview Conversation:
{self._get_full_conversation_context()}

Please provide a structured evaluation including:

1. Overall Score: X/10
2. Recommendation: (Hire/Don't Hire/Further Review)

Technical Skills:
[Detailed assessment of technical competencies mentioned]

Communication:
[Assessment of communication skills and clarity]

Strengths:
- [List key strengths demonstrated]

Areas for improvement:
- [List areas that need development]

Summary:
[2-3 paragraph summary of the candidate's performance and fit for the role]

Be specific, objective, and provide actionable feedback. Base your assessment only on what was discussed in the interview."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Please provide the interview evaluation."}
        ]
        
        summary = self._call_nvidia_api(messages, max_tokens=1500)
        
        if summary:
            logger.info(f"Generated interview summary: {len(summary)} characters")
            return summary
        else:
            # Fallback summary
            fallback = f"""Interview Summary for {self.config.get('position', 'Position')}

Overall Score: 6/10
Recommendation: Further Review

The candidate participated in a {self.questions_asked}-question interview covering {', '.join(self.focus_areas)}. 

Technical Skills: Assessment could not be completed due to technical issues.
Communication: The candidate was able to respond to questions during the interview.

Strengths:
- Participated in the full interview process
- Provided responses to all questions

Areas for improvement:
- Detailed technical assessment needed
- Further evaluation recommended

Summary: The interview was completed but requires manual review due to technical limitations in the AI evaluation system. Please review the full transcript for detailed assessment."""
            
            logger.warning("Using fallback summary due to API failure")
            return fallback
    
    def _get_conversation_context(self) -> str:
        """Get recent conversation context for question generation."""
        recent_entries = self.conversation_history[-4:]  # Last 4 entries
        context_parts = []
        
        for entry in recent_entries:
            if entry.get('type') == 'question':
                context_parts.append(f"Previous Question: {entry['content']}")
            elif entry.get('type') == 'answer':
                context_parts.append(f"Candidate Response: {entry['content'][:200]}...")
        
        return '\n'.join(context_parts)
    
    def _get_full_conversation_context(self) -> str:
        """Get full conversation context for summary generation."""
        context_parts = []
        
        for i, entry in enumerate(self.conversation_history):
            if entry.get('type') == 'question':
                context_parts.append(f"Question {i//2 + 1}: {entry['content']}")
            elif entry.get('type') == 'answer':
                context_parts.append(f"Answer: {entry['content']}")
        
        return '\n\n'.join(context_parts)