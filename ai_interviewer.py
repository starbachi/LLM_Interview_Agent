import json, logging, yaml, requests, re

from typing import Dict, Any, List, Optional

from config_manager import config

logger = logging.getLogger("ai_interviewer")
logger.setLevel(getattr(logging, config.get("logging.level", "DEBUG")))
handler = logging.FileHandler(config.get("logging.file", "interview_debug.log"))
handler.setFormatter(logging.Formatter(config.get("logging.format", "%(asctime)s [%(levelname)s] %(message)s")))
if not logger.handlers:
    logger.addHandler(handler)

# Load YAML of the prompts
with open("configs/prompts.yaml", "r") as f:
    prompts = yaml.safe_load(f)

class AIInterviewer:
    """AI-powered interviewer using NVIDIA NIM Llama 4 Maverick model."""
    
    def __init__(self, interview_config: Dict[str, Any]):
        """
        Initialize the AI interviewer.
        
        Args:
            interview_config: Configuration for the interview
        """
        self.config = interview_config
        self.conversation_history: List[Dict[str, Optional[str]]] = []
        self.questions_asked = 0
        self.max_questions = interview_config.get('question_count', 10)
        
        self.user_responses: List[str] = []
        
        # Load NVIDIA API configuration
        self.api_key = self._load_nvidia_api_key()
        self.base_url = "https://integrate.api.nvidia.com/v1"
        
        logger.info(f"AI Interviewer initialized for position: {self.config.get('position', 'Unknown')}")
    
    def __prepare_yaml_entry(self, entry_key: str, **extra_vars) -> str:
        """
        Takes a YAML entry key and substitutes placeholders
        with values from global config + optional extra variables.
        """
        if entry_key not in prompts:
            raise KeyError(f"Entry '{entry_key}' not found in prompts.yaml")
    
        template = prompts[entry_key]
    
        # --- Replace {config.get('key', 'default')} ---
        def repl_config(match):
            key = match.group(1)
            default = match.group(2) if match.group(2) else ''
            return str(self.config.get(key, default))
    
        template = re.sub(
            r"\{config\.get\('([^']+)'(?:,\s*'([^']*)')?\)\}",
            repl_config,
            template,
        )
    
        # --- Replace {', '.join(config.get('list_key', []))} ---
        def repl_list(match):
            key = match.group(1)
            value = self.config.get(key, [])
            if isinstance(value, list):
                return ", ".join(value)
            return str(value)
    
        template = re.sub(
            r"\{', '\.join\(config\.get\('([^']+)', \[\]\)\)\}",
            repl_list,
            template,
        )
        
        def repl_simple_config(match):
            key = match.group(1)
            value = self.config.get(key, '')
            if isinstance(value, list):
                return ", ".join(value)
            return str(value)
        
        template = re.sub(
            r"\{config\.get\('([^']+)'\)\}",
            repl_simple_config,
            template,
        )
    
        # --- Replace any extra variables {var} ---
        for k, v in extra_vars.items():
            template = template.replace(f"{{{k}}}", str(v))
    
        return template
    
    def __conversation_history_handler(self, role: str, content: str, type: str):
            self.conversation_history.append({
                "role": role,
                "content": content,
                "type": type,
            })

    def _load_nvidia_api_key(self) -> str:
        """Load NVIDIA API key from environment file."""
        import os
        from dotenv import load_dotenv
        
        env_file_path = os.path.join(os.path.dirname(__file__), 'helpers/api', 'api.env')
        if os.path.exists(env_file_path):
            load_dotenv(env_file_path)
            api_key = os.getenv('NVIDIA_API_KEY')
            if api_key:
                logger.debug("NVIDIA API key loaded successfully")
                return api_key
        
        logger.error("NVIDIA API key not found")
        raise RuntimeError("NVIDIA_API_KEY not set in helpers/api/api.env")
    
    def _call_nvidia_api(self, message: List[Dict[str, str]], max_tokens: int = 500) -> Optional[str]:
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
            "model": "meta/llama-4-maverick-17b-128e-instruct",
            "messages": message,
            "max_tokens": max_tokens,
            "temperature": 0.1,
            "top_p": 0.9,
            "stream": False
        }
        
        
        try:
            logger.debug(f"Calling NVIDIA API with {len(message)} messages")
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

        # Get the prompt template from yaml
        system_prompt = self.__prepare_yaml_entry("introduction_prompt")
        user_prompt = self.__prepare_yaml_entry("introduction_prompt_user")

        # Prepare message for NVIDIA API
        message = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        
        # Call NVIDIA API
        introduction = self._call_nvidia_api(message, max_tokens=200)
        
        # If API returned a valid introduction, use it
        if introduction:
            self.__conversation_history_handler("assistant", introduction, "introduction")
            logger.info(f"Generated introduction: {introduction[:20]}...")  
            return introduction
        else:
            # Else, use fallback introduction
            fallback = self.__prepare_yaml_entry("fallback_introduction")
            self.__conversation_history_handler("assistant", fallback, "introduction")
            logger.warning(f"Using fallback introduction due to API failure: {fallback[:20]}...")
            return fallback
    
    def get_next_question(self) -> Optional[str]:
        """Generate the next interview question."""
        if self.questions_asked >= self.max_questions:
            logger.info("Maximum questions reached, ending interview")
            return None

        # Get prompt template from yaml
        system_prompt = self.__prepare_yaml_entry("question_generation", 
                                                    questions_asked=self.questions_asked, 
                                                    max_questions=self.max_questions, 
                                                    conversation_context=self._get_conversation_context())

        user_prompt = self.__prepare_yaml_entry("question_generation_user")

        # Prepare message for NVIDIA API
        message = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        
        # Call NVIDIA API
        question = self._call_nvidia_api(message, max_tokens=300)
        
        # If API returned a valid question, use it
        if question:
            question = question.strip()
            self.__conversation_history_handler("assistant", question, "question")
            self.questions_asked += 1
            logger.info(f"Generated question {self.questions_asked}: {question[:20]}...")
            return question
        else:
            # Ensure we don't go beyond available fallback questions (1-10)
            fallback_index = min(self.questions_asked + 1, 10)
            which_fallback_question = f"fallback_question_{fallback_index}"
            
            try:
                fallback_question = self.__prepare_yaml_entry(which_fallback_question)
            except KeyError:
                # If we run out of fallback questions, use a generic one
                fallback_question = "Can you tell me more about your experience and qualifications for this role?"
                logger.warning(f"No fallback question available for index {fallback_index}, using generic question")
            
            self.__conversation_history_handler("assistant", fallback_question, "question")
            self.questions_asked += 1
            logger.warning(f"Using fallback question")
            return fallback_question
    
    def process_answer(self, answer: str) -> None:
        """
        Process the user's answer and store it.
        
        Args:
            answer: User's response to the current question
        """
        if answer and answer.strip():
            self.user_responses.append(answer.strip())
            self.__conversation_history_handler("user", answer.strip(), "answer")
            logger.info(f"Processed user answer: {len(answer)} characters")
        else:
            logger.warning("Empty or invalid answer received")
    
    def rephrase_question(self, original_question: str) -> str:
        """
        Rephrase the current question to make it simpler or clearer.
        
        Args:
            original_question: The original question to rephrase
            
        Returns:
            Rephrased question or None if failed
        """
        # Get the prompt template from yaml
        system_prompt = self.__prepare_yaml_entry("rephrase_question", original_question = original_question)
        user_prompt = self.__prepare_yaml_entry("rephrase_question_user", original_question = original_question)

        # Prepare message for NVIDIA API
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        
        # Call NVIDIA API
        rephrased = self._call_nvidia_api(messages, max_tokens=200)
        
        # If API returned a valid rephrased question, use it
        if rephrased:
            rephrased = rephrased.strip()
            logger.info(f"Rephrased question: {rephrased[:20]}...")
            return rephrased
        else:
            logger.warning("Failed to rephrase question, returning original")
            return original_question
    
    def generate_summary(self) -> str:
        """Generate a comprehensive interview summary and evaluation."""
        if not self.user_responses:
            logger.warning("No user responses to summarize")
            return "No responses were recorded during the interview."
        
        # Get the prompt template from yaml
        system_prompt = self.__prepare_yaml_entry("summarise_interview", 
                                                  questions_asked = self.questions_asked,
                                                  conversation_context=self._get_full_conversation_context())

        user_prompt = self.__prepare_yaml_entry("summarise_interview_user",
                                                conversation_context=self._get_full_conversation_context())
        # Prepare message for NVIDIA API        
        message = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        
        # Call NVIDIA API        
        summary = self._call_nvidia_api(message, max_tokens=1500)
        
        # If API returned a valid summary, use it
        if summary:
            logger.info(f"Generated interview summary: {len(summary)} characters")
            return summary
        else:
            # Else, use fallback summary
            fallback = self.__prepare_yaml_entry("fallback_summary")
            logger.warning("Using fallback summary due to API failure")
            return fallback
    
    def _get_conversation_context(self) -> str:
        """Get recent conversation context for question generation."""
        recent_entries = self.conversation_history[-4:]  # Last 4 entries
        context_parts = []
        
        for entry in recent_entries:
            entry_type = entry.get('type')
            content = entry.get('content')
            
            if entry_type == 'question':
                # Ensure we never try to slice a None; provide a placeholder if missing
                content_text = content if isinstance(content, str) and content else "[No question text]"
                context_parts.append(f"Previous Question: {content_text}")
            elif entry_type == 'answer':
                # Safely handle None/non-string and truncate long answers
                if isinstance(content, str) and content:
                    snippet = content[:200] + ("..." if len(content) > 200 else "")
                else:
                    snippet = "[No response]"
                context_parts.append(f"Candidate Response: {snippet}")
        
        return '\n'.join(context_parts)
    
    def _get_full_conversation_context(self) -> str:
        """Get full conversation context for summary generation."""
        context_parts = []
        
        for i, entry in enumerate(self.conversation_history):
            entry_type = entry.get('type')
            content = entry.get('content')
            content_text = content if isinstance(content, str) and content else "[No response]"
            
            if entry_type == 'question':
                context_parts.append(f"Question {i//2 + 1}: {content_text}")
            elif entry_type == 'answer':
                context_parts.append(f"Answer: {content_text}")
        
        return '\n\n'.join(context_parts)