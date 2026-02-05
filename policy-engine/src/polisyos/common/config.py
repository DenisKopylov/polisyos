import multiprocessing
import os
import sys

from dotenv import load_dotenv
from loguru import logger

# JAX настройки ДО любого импорта JAX
os.environ["JAX_PLATFORM_NAME"] = "cpu"
os.environ["JAX_ENABLE_X64"] = "false"
os.environ["JAX_DISABLE_MOST_OPTIMIZATIONS"] = "true"
os.environ["JAX_CHECK_TRACER_LEAKS"] = "false"

# 1. Загружаем переменные из .env
load_dotenv()

# --- HARDWARE SAFEGUARDS (Защита железа) ---

# Определяем количество физических ядер
total_cores = multiprocessing.cpu_count()

# Рассчитываем безопасное число ядер (оставляем резерв системе ~20% или минимум 1 ядро)
reserved_cores = max(1, int(total_cores * 0.20))
allowed_cores = max(1, total_cores - reserved_cores)

# --- ПРИМЕНЕНИЕ НАСТРОЕК JAX ---
# Важно: Это должно произойти ДО первого import jax в проекте!

# 1. Отключаем жадную аллокацию памяти (если не задано в .env)
if "XLA_PYTHON_CLIENT_PREALLOCATE" not in os.environ:
    os.environ["XLA_PYTHON_CLIENT_PREALLOCATE"] = "false"

# 2. Ограничиваем потоки CPU (если не задано в .env)
if "XLA_FLAGS" not in os.environ:
    # intra_op_parallelism_threads ограничивает "тяжелые" вычисления внутри одной операции
    flags = f"--xla_cpu_multi_thread_eigen=true intra_op_parallelism_threads={allowed_cores}"
    os.environ["XLA_FLAGS"] = flags
    logger.info(f"⚙️ Auto-configured JAX CPU Limit: {allowed_cores}/{total_cores} cores")
else:
    logger.info(f"⚙️ Using .env JAX Flags: {os.environ['XLA_FLAGS']}")

logger.info(f"⚙️ Memory Safeguard: Preallocate={os.environ.get('XLA_PYTHON_CLIENT_PREALLOCATE')}")

# --- SCIENTIST / TORCH SAFEGUARDS ---
# Для MacBook Air M2 и аналогичных машин держим BO/GP на CPU по умолчанию.
os.environ.setdefault("SCIENTIST_TORCH_DEVICE", "cpu")
os.environ.setdefault("SCIENTIST_TORCH_NUM_THREADS", str(allowed_cores))
os.environ.setdefault("SCIENTIST_TORCH_NUM_INTEROP_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", str(allowed_cores))
os.environ.setdefault("OPENBLAS_NUM_THREADS", str(allowed_cores))
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", str(allowed_cores))
os.environ.setdefault("NUMEXPR_NUM_THREADS", str(allowed_cores))

logger.info(
    "⚙️ Scientist Torch defaults: device={}, threads={}, interop={}",
    os.environ.get("SCIENTIST_TORCH_DEVICE"),
    os.environ.get("SCIENTIST_TORCH_NUM_THREADS"),
    os.environ.get("SCIENTIST_TORCH_NUM_INTEROP_THREADS"),
)

# --- APP SETTINGS ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")
DUCKDB_MEMORY_LIMIT = os.getenv("DUCKDB_MEMORY_LIMIT", "4GB")
# Используем allowed_cores как дефолт для DuckDB, если не задано иное
DUCKDB_THREADS = int(os.getenv("DUCKDB_THREADS", allowed_cores))

# --- LOGGER SETUP ---
# Сбрасываем дефолтную конфигурацию
logger.remove()

# 1. Консоль (Красивый вывод для разработчика)
logger.add(
    sys.stderr,
    level=LOG_LEVEL,
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    ),
)

# 2. Файл (JSON для аудита/парсинга машинами)
# rotation="10 MB" создаст новый файл, когда лог достигнет 10МБ
logger.add(
    "logs/system.log",
    rotation="10 MB",
    retention="10 days",
    serialize=True,
    level="INFO",
    encoding="utf-8",
)
