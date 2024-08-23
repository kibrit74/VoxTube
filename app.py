import os
import logging
import traceback
import base64
import io
import re
import time
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
from gtts import gTTS
from gtts.tts import gTTSError
import uvicorn
from pydantic import BaseModel, HttpUrl

# Logging configuration
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# API and Module Configuration
GEMINI_API_KEY = "AIzaSyDcwWntCfE6kxleEuxJqBHVvJ0-WErzamE"
genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel('gemini-1.5-flash')

# FastAPI Application
app = FastAPI(debug=True)

# CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TranslationRequest(BaseModel):
    video_url: HttpUrl
    transcript: str

def translate_with_gemini(transcript: str) -> List[Dict[str, Any]]:
    """Translates text from any language to Turkish using Google Gemini."""
    prompt = f"""Lütfen aşağıdaki YouTube video transkriptini Türkçe'ye çevirin. Transkriptin hangi dilde olduğunu otomatik olarak algılayın. Özetlemeyin, sadece konuşmacının sözlerini doğrudan çevirin. Zaman damgalarını ve '[Music]' işaretlerini '[Müzik]' olarak çevirin. Çeviriyi aşağıdaki formatta döndürün:

    0:00 Çevrilmiş metin
    0:05 [Müzik]
    0:10 Diğer çevrilmiş metin
    ...

    İşte çevrilecek transkript:
    {transcript}
    """

    try:
        response = model.generate_content(prompt)
        if not response.text:
            raise ValueError("Gemini API'den boş yanıt")
        
        logger.debug(f"Raw response from Gemini: {response.text}")
        
        lines = response.text.strip().split('\n')
        translated_segments = []
        
        for line in lines:
            match = re.match(r'^(\d+:\d+)\s+(.+)$', line.strip())
            if match:
                time_str, text = match.groups()
                start_time = time_to_seconds(time_str)
                translated_segments.append({
                    'start': start_time,
                    'end': start_time + 5,  # Assuming each segment is 5 seconds long
                    'text': text.strip()
                })
        
        if not translated_segments:
            raise ValueError("Çeviri sonucu boş veya geçersiz format")

        return translated_segments
    except Exception as e:
        logger.error(f"Translation error: {str(e)}")
        logger.error(traceback.format_exc())
        raise ValueError(f"Çeviri sırasında hata: {str(e)}")

def process_transcript(transcript: str) -> List[Dict[str, Any]]:
    """Processes YouTube transcript and extracts timestamps."""
    logger.info(f"Incoming transcript:\n{transcript}")
    try:
        lines = transcript.split('\n')
        processed_lines = []
        current_timestamp = None
        current_text = ""
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            logger.debug(f"Processing line {line_num}: {line}")
            if not line:
                continue
            match = re.match(r'^([\d:]+)', line)
            if match:
                if current_timestamp is not None and current_text:
                    processed_lines.append({
                        'start': current_timestamp,
                        'end': time_to_seconds(match.group(1)),
                        'text': current_text.strip()
                    })
                    logger.debug(f"Added segment: {processed_lines[-1]}")
                current_timestamp = time_to_seconds(match.group(1))
                current_text = line[len(match.group(1)):].strip()
            elif current_timestamp is not None:
                current_text += " " + line
        if current_timestamp is not None and current_text:
            processed_lines.append({
                'start': current_timestamp,
                'end': current_timestamp + 5,
                'text': current_text.strip()
            })
            logger.debug(f"Added last segment: {processed_lines[-1]}")
        if not processed_lines:
            raise ValueError("No valid transcript lines found")
        
        final_lines = []
        for i in range(len(processed_lines)):
            final_lines.append(processed_lines[i])
            if i < len(processed_lines) - 1:
                gap = processed_lines[i+1]['start'] - processed_lines[i]['end']
                if gap > 0:
                    final_lines.append({
                        'start': processed_lines[i]['end'],
                        'end': processed_lines[i+1]['start'],
                        'text': '[Müzik]'
                    })
        
        logger.info(f"Processed transcript: {final_lines}")
        return final_lines
    except Exception as e:
        logger.error(f"Error processing transcript: {str(e)}")
        logger.error(traceback.format_exc())
        raise ValueError(f"Error processing transcript: {str(e)}")

def time_to_seconds(time_str: str) -> float:
    """Converts time string to seconds."""
    try:
        time_str = re.sub(r'[^\d:]', '', time_str)
        
        if time_str.isdigit():
            return float(time_str)
        
        parts = time_str.split(':')
        if len(parts) == 1:
            return float(parts[0])
        elif len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
        elif len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        else:
            raise ValueError("Invalid time format")
    except ValueError as e:
        logger.error(f"Invalid time format: {time_str}")
        raise ValueError(f"Invalid time format: {time_str}")

def generate_audio_with_retry(text: str, max_retries: int = 3, delay: int = 5) -> io.BytesIO:
    """Generates audio with retry mechanism using gTTS."""
    for attempt in range(max_retries):
        try:
            audio_io = io.BytesIO()
            tts = gTTS(text=text, lang='tr', slow=False)
            tts.write_to_fp(audio_io)
            audio_io.seek(0)
            return audio_io
        except gTTSError as e:
            if attempt == max_retries - 1:
                raise
            logger.warning(f"gTTS generation failed. Retrying in {delay} seconds. Error: {str(e)}")
            time.sleep(delay)

@app.post("/translate")
async def translate(request: TranslationRequest):
    """Translates video information and creates an audio file."""
    try:
        logger.info(f"Received translation request - Video URL: {request.video_url}")

        processed_transcript = process_transcript(request.transcript)
        translated_segments = translate_with_gemini("\n".join([f"{seg['start']:.2f} {seg['text']}" for seg in processed_transcript]))

        logger.debug(f"Translation result: {translated_segments}")

        if not translated_segments:
            raise ValueError("Çeviri sonucu boş")

        logger.info("Translation completed, generating audio")

        audio_io = io.BytesIO()
        valid_segments = [seg for seg in translated_segments if seg['text'].strip() and seg['text'] != '[Müzik]']
        
        if not valid_segments:
            raise ValueError("Ses dosyası oluşturmak için geçerli metin segmenti bulunamadı")

        for segment in valid_segments:
            try:
                if segment['text'].strip():
                    segment_audio = generate_audio_with_retry(segment['text'])
                    audio_io.write(segment_audio.getvalue())
            except gTTSError as e:
                logger.error(f"Error generating audio for segment: {segment}. Error: {str(e)}")
                continue

        if audio_io.getbuffer().nbytes == 0:
            raise ValueError("Ses dosyası oluşturulamadı")

        audio_io.seek(0)
        audio_base64 = base64.b64encode(audio_io.read()).decode('utf-8')

        logger.info("Audio file created and converted to base64")

        video_id = str(request.video_url).split("v=")[1] if "v=" in str(request.video_url) else str(request.video_url).split("/")[-1]

        return JSONResponse(content={
            "video_id": video_id,
            "audio_data": audio_base64,
            "segments": translated_segments
        })
        
    except ValueError as ve:
        logger.error(f"Value error: {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error in translation function: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@app.get("/")
async def read_root():
    with open("index.html", "r") as file:
        html_content = file.read()
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860, log_level="info")
