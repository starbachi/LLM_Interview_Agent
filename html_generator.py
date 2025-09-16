import time, re
from datetime import datetime
from typing import Dict, Any, Optional

def generate_html_report(interview_data: Dict[str, Any], template_path: str = "interview_report_template.html") -> str:
    """Generate HTML report from interview data"""
    
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            template = f.read()
    except FileNotFoundError:
        return "<html><body><h1>Error: Template file not found</h1></body></html>"
    
    # Extract data from interview results
    job_desc = interview_data.get('job_position', '')
    summary = interview_data.get('interview_summary', '') or ''  # Handle None case
    transcript = interview_data.get('transcript', [])
    
    # Parse job description
    position = "Placeholder Position"
    company = "Placeholder Company"
    department = "Placeholder Department"
    level = "Placeholder Level"
    skills = "Placeholder Skills"
    job_description = "Placeholder Job Description"
    
    if 'Position:' in job_desc:
        parts = job_desc.split(' at ')
        if len(parts) >= 2:
            position = parts[0].replace('Position:', '').strip()
            company = parts[1].strip()
    
    # Extract scores and assessments from summary
    overall_score = extract_score(summary)
    recommendation = extract_recommendation(summary)
    technical_assessment = extract_section(summary, "Technical Skills")
    communication_assessment = extract_section(summary, "Communication")
    strengths = extract_list_items(summary, "Strengths")
    improvements = extract_list_items(summary, "Areas for improvement")
    
    # Add a fallback message if summary is empty
    if not summary.strip():
        summary = "Interview summary generation failed. Please check the AI service configuration and try generating the report again."
    
    # Generate transcript HTML
    transcript_html = generate_transcript_html(transcript)
    
    # Format dates
    current_date = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    interview_date = datetime.fromtimestamp(interview_data.get('timestamp', time.time())).strftime("%B %d, %Y")
    
    # Determine recommendation class
    rec_class = "recommend-review"
    if "hire" in recommendation.lower() and "don't" not in recommendation.lower():
        rec_class = "recommend-hire"
    elif "don't hire" in recommendation.lower() or "reject" in recommendation.lower():
        rec_class = "recommend-reject"
    
    # Prepare replacement values
    replacements = {
        '{{position}}': position,
        '{{company}}': company,
        '{{department}}': department,
        '{{level}}': level,
        '{{skills}}': skills,
        '{{job_description}}': job_description,
        '{{date}}': current_date,
        '{{overall_score}}': str(overall_score),
        '{{score_description}}': get_score_description(overall_score),
        '{{recommendation}}': recommendation,
        '{{recommendation_class}}': rec_class,
        '{{interview_summary}}': summary,
        '{{technical_assessment}}': technical_assessment,
        '{{communication_assessment}}': communication_assessment,
        '{{strengths_list}}': strengths,
        '{{improvements_list}}': improvements,
        '{{transcript_content}}': transcript_html,
        '{{interview_date}}': interview_date,
        '{{generation_date}}': current_date,
        '{{total_questions}}': str(len([t for t in transcript if t.get('type') == 'question'])),
        '{{interview_id}}': f"INT_{int(time.time())}",
        '{{duration}}': str(round(len(transcript) * 2.5))  # Estimate duration
    }
    
    # Apply replacements
    html_content = template
    for placeholder, value in replacements.items():
        # Ensure value is a string and handle None/empty cases
        if value is None:
            value = "Not available"
        elif not isinstance(value, str):
            value = str(value)
        html_content = html_content.replace(placeholder, value)
    
    return html_content

def extract_score(text: str) -> int:
    """Extract numerical score from text"""
    if not text or not isinstance(text, str):
        return -1  # Default score for missing summary
        
    patterns = [
        r'score[:\s]+(\d+)/10',
        r'(\d+)\s*out of 10',
        r'rating[:\s]+(\d+)',
        r'Overall[:\s]+(\d+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    
    return -1  # Default score

def extract_recommendation(text: str) -> str:
    """Extract recommendation from text"""
    if not text or not isinstance(text, str):
        return "Further Review Recommended"
        
    patterns = [
        r'Recommendation[:\s]+(.*?)(?:\n|$)',
        r'recommend[:\s]+(.*?)(?:\n|$)',
        r'(hire|don\'t hire|further review)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return "Further Review Recommended"

def extract_section(text: str, section_name: str) -> str:
    """Extract specific section content"""
    if not text or not isinstance(text, str):
        return f"{section_name} assessment not available - summary generation failed."
        
    pattern = rf'{section_name}[:\s]+(.*?)(?:\n\n|\n[A-Z]|$)'
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    
    if match:
        return match.group(1).strip()
    
    return f"{section_name} assessment not available in the provided summary."

def extract_list_items(text: str, section_name: str) -> str:
    """Extract list items and format as HTML"""
    if not text or not isinstance(text, str):
        return f'<li>No specific {section_name.lower()} identified - summary generation failed.</li>'
        
    section_text = extract_section(text, section_name)
    
    # Look for bullet points or numbered lists
    lines = section_text.split('\n')
    list_items = []
    
    for line in lines:
        line = line.strip()
        if line and (line.startswith('-') or line.startswith('•') or line.startswith('*') or 
                    (len(line) > 0 and line[0].isdigit() and '.' in line[:3])):
            # Remove bullet point or number
            clean_line = re.sub(r'^[-•*]\s*', '', line)
            clean_line = re.sub(r'^\d+\.\s*', '', clean_line)
            if clean_line:
                list_items.append(f'<li>{clean_line}</li>')
    
    if not list_items:
        # If no clear list format, treat each sentence as an item
        sentences = re.split(r'[.!?]+', section_text)
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and len(sentence) > 10:
                list_items.append(f'<li>{sentence}</li>')
    
    return '\n'.join(list_items) if list_items else f'<li>No specific {section_name.lower()} identified in the assessment.</li>'

def generate_transcript_html(transcript: list) -> str:
    """Generate HTML for transcript"""
    html_parts = []
    
    for entry in transcript:
        entry_type = entry.get('type', 'unknown')
        content = entry.get('content', '')
        
        if entry_type == 'greeting':
            html_parts.append(f'''
            <div class="transcript-item greeting">
                <strong>Interviewer Introduction</strong>
                {content}
            </div>
            ''')
        elif entry_type == 'question':
            html_parts.append(f'''
            <div class="transcript-item question">
                <strong>Question</strong>
                {content}
            </div>
            ''')
        elif entry_type == 'answer':
            html_parts.append(f'''
            <div class="transcript-item answer">
                <strong>Candidate Response</strong>
                {content}
            </div>
            ''')
    
    return '\n'.join(html_parts) if html_parts else '<p>No transcript available.</p>'

def get_score_description(score: int) -> str:
    """Get description for numerical score"""
    if score >= 9:
        return "Exceptional Performance"
    elif score >= 8:
        return "Excellent Performance"
    elif score >= 7:
        return "Good Performance"
    elif score >= 6:
        return "Satisfactory Performance"
    elif score >= 5:
        return "Needs Improvement"
    else:
        return "Below Expectations"

def save_html_report(interview_data: Dict[str, Any], output_path: Optional[str] = None) -> str:
    """Generate and save HTML report"""
    if not output_path:
        timestamp = int(time.time())
        output_path = f"interview_report_{timestamp}.html"
    
    html_content = generate_html_report(interview_data)
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        return output_path
    except Exception as e:
        print(f"Error saving HTML report: {e}")
        return ""