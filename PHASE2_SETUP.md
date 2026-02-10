# NotesOS Phase 2 - Setup Guide

## Prerequisites

1. **PostgreSQL with pgvector**
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

2. **Redis** (for job queues)
   - Running on default port 6379

3. **Tesseract OCR** (for image text extraction)
   - Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
   - Linux: `sudo apt-get install tesseract-ocr`
   - Mac: `brew install tesseract`

4. **Poppler** (for PDF processing)
   - Windows: Download from https://github.com/oschwartz10612/poppler-windows/releases
   - Linux: `sudo apt-get install poppler-utils`
   - Mac: `brew install poppler`

## Environment Variables

Create `.env` in `backend/` directory:

```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/notesos
REDIS_URL=redis://localhost:6379

# JWT
JWT_SECRET=your-super-secret-jwt-key-change-this
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080

# AI Services
DEEPSEEK_API_KEY=your-deepseek-api-key
OPENAI_API_KEY=your-openai-api-key
SERPER_API_KEY=your-serper-api-key-for-search

# Cloudinary (File Storage)
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=your-api-key
CLOUDINARY_API_SECRET=your-api-secret

# Settings
CORS_ORIGINS=["http://localhost:3000"]
PRIMARY_AI_PROVIDER=deepseek
ENABLE_OCR_CLEANING=true
```

## Installation

1. **Install Python dependencies**:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Run database migrations**:
   ```bash
   alembic upgrade head
   ```

3. **Start Redis** (if not already running):
   ```bash
   redis-server
   ```

## Running the Application

### 1. Start the API Server
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Start the Background Worker
In a separate terminal:
```bash
cd backend
python -m app.workers.chunking_worker
```

## API Endpoints

### Topics
- `GET /api/courses/{course_id}/topics` - List topics
- `POST /api/courses/{course_id}/topics` - Create topic
- `GET /api/topics/{topic_id}` - Get topic
- `PUT /api/topics/{topic_id}` - Update topic
- `DELETE /api/topics/{topic_id}` - Delete topic

### Notes
- `GET /api/topics/{topic_id}/notes` - List notes (paginated)
- `POST /api/topics/{topic_id}/notes` - Create text note
- `POST /api/notes/upload` - Upload file note (PDF/DOCX/Image)
  - Form data: `topic_id`, `title`, `file`, optional `is_handwritten`
- `GET /api/notes/{note_id}` - Get note
- `PUT /api/notes/{note_id}` - Update note
- `DELETE /api/notes/{note_id}` - Delete note

### WebSocket
- `WS /ws/{course_id}?token={jwt_token}` - Real-time course updates

## Testing File Upload

Using cURL:
```bash
# Upload a PDF
curl -X POST http://localhost:8000/api/notes/upload \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "topic_id=TOPIC_UUID" \
  -F "title=My Notes" \
  -F "file=@path/to/file.pdf"

# Upload handwritten image (OCR cleaning enabled)
curl -X POST http://localhost:8000/api/notes/upload \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "topic_id=TOPIC_UUID" \
  -F "title=Handwritten Notes" \
  -F "is_handwritten=true" \
  -F "file=@path/to/handwriting.jpg"
```

## Monitoring

### Check job queue status:
```bash
redis-cli
> LLEN queue:chunking  # See pending jobs
> HGETALL job:JOB_ID   # Check specific job status
```

### Check note processing:
```sql
SELECT id, title, is_processed, ocr_cleaned FROM notes;
SELECT COUNT(*) FROM note_chunks WHERE note_id = 'NOTE_ID';
```

## Troubleshooting

### Issue: OCR not working
- Ensure Tesseract is installed and in PATH
- Test: `tesseract --version`

### Issue: PDF processing fails
- Ensure Poppler is installed
- Windows: Add poppler/bin to PATH

### Issue: Background worker not processing
- Check Redis is running: `redis-cli ping`
- View worker logs for errors
- Verify job was enqueued: `redis-cli LLEN queue:chunking`

### Issue: File upload fails
- Check Cloudinary credentials in `.env`
- Verify file size limits (default 10MB in FastAPI)

## Next Steps (Phase 3)

- [ ] AI Chat with RAG
- [ ] Quiz Generation
- [ ] Fact-Checking
- [ ] Voice Grading
- [ ] Pre-Class Research
