import logging

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    ChatContext,
    ChatMessage,
    JobContext,
    JobProcess,
    cli,
    inference,
    room_io,
)
from livekit.plugins import noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")

INFORMATICS_ONLY_INSTRUCTIONS = """
You are a specialized voice AI assistant for Informatics, Computer Science, and Information Technology only.

Your allowed scope includes:
- programming
- software engineering
- algorithms and data structures
- databases and SQL
- operating systems
- computer networks
- cybersecurity
- artificial intelligence and machine learning
- web development
- APIs and backend/frontend development
- cloud computing
- DevOps
- debugging and technical troubleshooting
- system design
- software architecture

Rules:
1. Answer only questions related to informatics, computer science, software, IT, and technical engineering.
2. If the user asks about anything outside this scope, politely refuse.
3. For out-of-scope questions, reply with:
   "I am specialized in informatics and technical subjects only. Please ask me about programming, software engineering, networks, databases, AI, cloud, cybersecurity, or related IT topics."
4. Keep answers concise, clear, and practical for voice interaction.
5. Do not use emojis or decorative formatting.
6. Do not invent facts. If something is uncertain, say so clearly.
7. When useful, explain step by step.
8. Prefer technical precision over casual conversation.
9. If the user asks for code, provide correct and maintainable code.
10. Respond in the same language used by the user.
"""
ALLOWED_KEYWORDS = [
    "programming", "coding", "code", "python", "java", "javascript", "typescript",
    "c++", "c#", "php", "go", "rust", "html", "css", "react", "angular", "vue",
    "backend", "frontend", "full stack", "api", "rest", "graphql", "fastapi",
    "django", "flask", "node", "express",
    "software", "software engineering", "system design", "architecture", "microservices",
    "algorithm", "algorithms", "data structure", "data structures",
    "database", "databases", "sql", "mysql", "postgres", "postgresql", "mongodb", "redis",
    "operating system", "linux", "windows", "kernel", "thread", "process",
    "network", "networks", "tcp", "udp", "ip", "dns", "routing", "switching", "subnet",
    "cybersecurity", "security", "authentication", "authorization", "encryption", "oauth", "jwt",
    "ai", "artificial intelligence", "machine learning", "deep learning", "neural network",
    "cloud", "azure", "aws", "gcp", "docker", "kubernetes", "devops", "ci/cd",
    "debug", "bug", "troubleshooting", "deployment", "server", "client",
    "computer science", "informatics", "information technology", "it",
    "برمجة", "كود", "معلوماتية", "هندسة برمجيات", "خوارزميات", "قواعد بيانات",
    "شبكات", "أمن سيبراني", "ذكاء اصطناعي", "تعلم آلة", "واجهة", "خلفية",
    "بايثون", "جافا", "جافاسكربت", "ريأكت", "لينكس", "ويندوز", "سحابة", "أزور"
]

OUT_OF_SCOPE_REPLY = (
    "I am specialized in informatics and technical subjects only. "
    "Please ask me about programming, software engineering, networks, "
    "databases, AI, cloud, cybersecurity, or related IT topics."
)


def is_informatics_question(text: str) -> bool:
    text = text.lower().strip()
    return any(keyword in text for keyword in ALLOWED_KEYWORDS)


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=INFORMATICS_ONLY_INSTRUCTIONS)


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session(agent_name="my-agent")
async def my_agent(ctx: JobContext):
    # Logging setup
    # Add any other context you want in all log entries here
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Join the room and connect to the user first to secure the room connection and avoid the 10-second timeout
    await ctx.connect()

    turn_detection = None
    try:
        turn_detection = MultilingualModel()
    except Exception as exc:
        logger.warning(
            "Turn detector unavailable; continuing without it. "
            "Run `uv run python src/agent.py download-files` to install model files. "
            "Error: %s",
            exc,
        )

    # Set up a voice AI pipeline using OpenAI, Cartesia, Deepgram, and the LiveKit turn detector
    session = AgentSession(
        # Speech-to-text (STT) is your agent's ears, turning the user's speech into text that the LLM can understand
        # See all available models at https://docs.livekit.io/agents/models/stt/
        stt=inference.STT(model="deepgram/nova-3", language="multi"),
        # A Large Language Model (LLM) is your agent's brain, processing user input and generating a response
        # See all available models at https://docs.livekit.io/agents/models/llm/
        llm=inference.LLM(model="openai/gpt-4.1-mini"),
        # Text-to-speech (TTS) is your agent's voice, turning the LLM's text into speech that the user can hear
        # See all available models as well as voice selections at https://docs.livekit.io/agents/models/tts/
        tts=inference.TTS(
            model="cartesia/sonic-3", voice="9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"
        ),
        # VAD and turn detection are used to determine when the user is speaking and when the agent should respond
        # See more at https://docs.livekit.io/agents/build/turns
        turn_detection=turn_detection,
        vad=ctx.proc.userdata["vad"],
        # allow the LLM to generate a response while waiting for the end of turn
        # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
        preemptive_generation=True,
    )

    # Start the session, which initializes the voice pipeline and warms up the models
    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind
                    == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)
