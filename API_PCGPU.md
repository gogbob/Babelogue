# Translator Audio Processing Service
## API Input/Output Specification

## 1. Overview

The audio processing service is a dedicated backend responsible for processing incoming audio, separating speakers, and identifying registered participants.

It communicates with the main translator backend through a REST API using FastAPI.

The service is responsible for:
- Receiving audio recordings and conversation chunks.
- Detecting speech and silence.
- Separating overlapping speakers.
- Extracting speaker embeddings.
- Identifying speakers using previously registered voice samples.
- Returning separated audio segments and associated metadata.

The main translator backend is responsible for:
- Managing users and conversations.
- Sending audio to the processing service.
- Managing conversation-wide timestamps and overlapping chunks.
- Transcribing and translating returned speech segments.
- Delivering results to the frontend.

### Models and technologies

| Component | Technology | Purpose |
|---|---|---|
| Speech separation | Fine-tuned MultiDecoderDPRNN | Separates multiple speakers |
| Speaker embeddings | SpeechBrain ECAPA-TDNN | Represents voice characteristics |
| Voice activity detection | Silero VAD | Detects speech regions |
| API | FastAPI | Handles HTTP requests |
| Audio processing | NumPy, SciPy, SoundFile | Audio loading and conversion |

---

# 2. Audio Input Specifications

The service accepts two types of audio input:

1. Speaker initialization recordings.
2. Normal conversation audio chunks.

### General audio requirements

- Audio must be in a format supported by SoundFile, such as WAV or FLAC.
- Audio is converted to mono during loading.
- Audio is internally represented as `float32`.
- The original sample rate is read from the uploaded file.
- Resampling is performed internally when required by the models.

Stereo recordings are converted to mono by averaging their channels.

## 2.1 Speaker Registration

At the beginning of a conversation, each participant is registered using an approximately five-second voice recording.

**Endpoint:**

`POST /conversations/{conversation_id}/speakers`

**Content type:** `multipart/form-data`

| Parameter | Type | Required | Description |
|---|---|---|---|
| `conversation_id` | String | Yes | Active conversation identifier |
| `speaker_id` | String | Yes | Unique participant identifier |
| `audio_file` | File | Yes | Participant's initialization recording |

**Input constraints:**
- Recording duration must be between 4.5 and 5.5 seconds.
- At least 3 seconds of speech must be detected.
- `speaker_id` must contain between 1 and 100 characters.
- The recording should contain the voice of the participant being registered.

The service extracts a 192-dimensional voice embedding and stores it in the conversation's temporary memory.

### Successful response

```json
{
  "conversation_id": "conversation-uuid",
  "speaker_id": "speaker_a",
  "status": "registered",
  "recording_duration": 5.0,
  "speech_duration": 4.2
}
```

| Field | Type | Description |
|---|---|---|
| `conversation_id` | String | Conversation identifier |
| `speaker_id` | String | Registered participant |
| `status` | String | Registration result |
| `recording_duration` | Float | Total recording duration in seconds |
| `speech_duration` | Float | Total detected speech duration in seconds |

Registration is explicit: unknown speakers encountered during normal processing are not automatically added to memory.

---

## 2.2 Conversation Audio Chunks

After participant registration, the main backend sends audio chunks for processing.

**Primary endpoint:**

`POST /conversations/{conversation_id}/chunks`

**Content type:** `multipart/form-data`

| Parameter | Type | Required | Description |
|---|---|---|---|
| `conversation_id` | String | Yes | Active conversation identifier |
| `audio_file` | File | Yes | Audio chunk to process |

**Input constraints:**
- Maximum duration: 10 seconds.
- Shorter chunks are accepted.
- Audio must be decodable by SoundFile.
- The conversation must already exist.

Recommended chunking configuration:

| Parameter | Value |
|---|---:|
| Chunk duration | 5 seconds |
| Hop duration | 2.5 seconds |
| Overlap | 2.5 seconds |

The overlap is handled by the main backend when reconciling results across chunks.

---

# 3. Audio Processing

Each submitted chunk is processed through the following stages:

1. **Voice Activity Detection:** Detects whether speech is present.
2. **Speaker Separation:** Separates the original mixture into individual speaker streams.
3. **Speech Region Detection:** Detects speech intervals within each separated stream.
4. **Embedding Extraction:** Generates a voice embedding for each sufficiently long speech segment.
5. **Speaker Identification:** Compares each embedding against the registered participants.
6. **Audio Encoding:** Encodes the extracted segments as WAV files.

Speaker identification uses cosine similarity against the registered voice embeddings.

The current similarity threshold is 0.4. Segments that do not match a registered participant are labelled `unknown`.

Segments shorter than one second cannot be reliably identified by the current embedding pipeline and may also be labelled `unknown`.

The service does not perform transcription or translation.

---

# 4. Audio Output Specifications

The chunk-processing endpoint returns a JSON object containing a list of separated speech segments.

**Response structure:**

```json
{
  "conversation_id": "conversation-uuid",
  "chunk_duration": 5.0,
  "segment_count": 2,
  "segments": [
    {
      "segment_id": "segment-uuid",
      "speaker_id": "speaker_a",
      "similarity": 0.87,
      "start": 0.5,
      "end": 2.8,
      "duration": 2.3,
      "stream_index": 0,
      "source": "separation",
      "sample_rate": 16000,
      "audio_format": "wav",
      "audio_wav_base64": "BASE64_ENCODED_AUDIO"
    },
    {
      "segment_id": "segment-uuid",
      "speaker_id": "speaker_b",
      "similarity": 0.91,
      "start": 2.1,
      "end": 4.6,
      "duration": 2.5,
      "stream_index": 1,
      "source": "separation",
      "sample_rate": 16000,
      "audio_format": "wav",
      "audio_wav_base64": "BASE64_ENCODED_AUDIO"
    }
  ]
}
```

*This is an illustrative response with example values. The field names and structure match the supplied `main.py`.*

## 4.1 Response Fields

### Chunk-level fields

| Field | Type | Description |
|---|---|---|
| `conversation_id` | String | Conversation identifier |
| `chunk_duration` | Float | Duration of the submitted chunk in seconds |
| `segment_count` | Integer | Number of returned speech segments |
| `segments` | Array | List of separated speech segments |

### Segment-level fields

| Field | Type | Description |
|---|---|---|
| `segment_id` | String | Unique identifier for the segment |
| `speaker_id` | String | Registered speaker ID or `unknown` |
| `similarity` | Float / null | Cosine similarity with the matched speaker |
| `start` | Float | Start time relative to the submitted chunk |
| `end` | Float | End time relative to the submitted chunk |
| `duration` | Float | Segment duration in seconds |
| `stream_index` | Integer | Index of the separator output stream |
| `source` | String | Processing source, such as `separation` or fallback processing |
| `sample_rate` | Integer | Output audio sample rate |
| `audio_format` | String | Audio format |
| `audio_wav_base64` | String | Base64-encoded WAV audio |

### Output audio format

The pipeline currently returns audio at 16 kHz.

The API encodes each segment as:
- Format: WAV
- Encoding: PCM 16-bit
- Channels: Mono
- Sample rate: 16,000 Hz

The audio is Base64-encoded to allow it to be transmitted within the JSON response.

The main backend can decode the audio as follows:

```python
import base64

audio_bytes = base64.b64decode(
    segment["audio_wav_base64"]
)
```

The resulting bytes can be saved as a WAV file or passed directly to a transcription service.

## 4.2 Timestamp Interpretation

Segment timestamps are relative to the beginning of the submitted chunk.

For example, if a chunk begins at 10 seconds in the conversation and a segment has:

```json
{
  "start": 1.2,
  "end": 3.4
}
```

Its conversation-wide timestamps are:

- Start: 11.2 seconds
- End: 13.4 seconds

The main backend is responsible for reconstructing the global timeline and reconciling overlapping chunks.

---

# 5. API Endpoint Reference

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | Basic service information |
| GET | `/health` | Service and model health |
| POST | `/conversations` | Create a conversation |
| POST | `/conversations/{id}/speakers` | Register a participant |
| POST | `/conversations/{id}/chunks` | Process an audio chunk |
| DELETE | `/conversations/{id}` | End a conversation and clear its memory |

Two additional routes are available as hidden aliases for chunk processing:

- `POST /conversations/{id}/identify`
- `POST /conversations/{id}/separate`

The recommended endpoint is `/chunks`.

## 5.1 Create Conversation

`POST /conversations`

Creates a new conversation and initializes its speaker memory.

Response:

```json
{
  "conversation_id": "conversation-uuid",
  "status": "created"
}
```

## 5.2 Health Check

`GET /health`

Returns the service status and hardware information.

Example:

```json
{
  "status": "ready",
  "models_loaded": true,
  "gpu_available": true,
  "gpu_name": "NVIDIA GeForce RTX 3060",
  "active_conversations": 1
}
```

## 5.3 End Conversation

`DELETE /conversations/{id}`

Deletes the conversation's registered voice embeddings and temporary memory.

Response:

```json
{
  "conversation_id": "conversation-uuid",
  "status": "ended"
}
```

---

# 6. Conversation Lifecycle

The intended interaction between the main backend and the audio service is:

1. Main backend creates a conversation.
2. Audio service returns a conversation ID.
3. Main backend registers each participant using their initialization recording.
4. Main backend sends audio chunks during the conversation.
5. Audio service returns separated speech segments and speaker metadata.
6. Main backend handles transcription, translation, and conversation history.
7. Main backend ends the conversation.
8. Audio service deletes the temporary speaker memory.

Speaker embeddings are stored in RAM and are not intended to persist beyond the conversation.

The service currently uses one model pipeline and serializes inference requests. It should run with a single Uvicorn worker because its conversation memory is process-local.

---

# 7. Main Backend Integration

The main backend should treat the audio service as a speech preprocessing component.

### Initialization

```text
POST /conversations
        |
        v
Receive conversation_id
        |
        v
POST /conversations/{id}/speakers
        |
        v
Register participant voice samples
```

### Normal processing

```text
Frontend audio
      |
      v
Main backend
      |
      v
Split into audio chunks
      |
      v
POST /conversations/{id}/chunks
      |
      v
Receive separated speech segments
      |
      v
Decode returned WAV audio
      |
      v
Reconcile overlapping segments
      |
      v
Transcription
      |
      v
Translation
      |
      v
Frontend
```

The audio service provides the main backend with the individual speech segments needed for downstream transcription and translation.

---

# 8. Dependencies

The FastAPI file-upload endpoints use multipart form data. Therefore, the following dependency must be included in `requirements.txt`:

```text
python-multipart
```

Install it with:

```bash
pip install python-multipart
```

The existing Docker image should then be rebuilt to include the dependency.

