import asyncio
import aiohttp
import os
import logging
import fire
from tqdm import tqdm
from aiohttp import ClientTimeout, ClientError
from dotenv import load_dotenv

load_dotenv()

DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "./ipsw_files")
DEFAULT_INTERVAL = int(os.environ.get("INTERVAL_CHECK","600"))
MAX_RETRIES = int(os.environ.get("DOWNLOAD_MAX_RETRIES", "3"))
DEVICES = os.environ["DEVICES"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("ipsw_monitor.log")]
)

def get_environment_devices():
    DEVICES = os.environ["DEVICES"]

async def fetch_json(session, url):
    """Realiza una petición GET asíncrona y devuelve el JSON."""
    async with session.get(url) as response:
        if response.status != 200:
            logging.error(f"❌ Error getting {url} - Status: {response.status}")
            return None
        return await response.json()

async def get_latest_ipsw(session, device):
    """Consulta la API de ipsw.me y devuelve la última versión disponible."""
    url = f"https://api.ipsw.me/v4/device/{device}?type=ipsw"
    data = await fetch_json(session, url)

    if not data or "firmwares" not in data:
        logging.error(f"Unable to get details for {device}")
        return None

    latest_firmware = data["firmwares"][0]  # El más reciente es el primero en la lista
    
    return {
        "device": data["name"],
        "identifier": device, 
        "version": latest_firmware["version"],
        "url": latest_firmware["url"]
    }

async def download_ipsw(session, device, version, url):
    """Descarga el archivo IPSW de forma asíncrona con manejo de timeouts y barra de progreso."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    filename = f"{device}_{version}.ipsw"
    filepath = os.path.join(DOWNLOAD_DIR, filename)

    timeout = ClientTimeout(total=None, sock_connect=60, sock_read=600)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logging.info(f"⬇️ Trying to download {filename} (attempt {attempt} of {MAX_RETRIES})...")

            # Usamos HEAD para obtener el tamaño del archivo
            async with session.head(url, timeout=timeout) as response:
                if response.status != 200:
                    raise Exception(f"❌ HEAD falló con status {response.status}")
                total_size = int(response.headers.get("Content-Length", 0))

            if total_size == 0:
                logging.error(f"❌ File size {filename} cannot be determined.")
                return

            with tqdm(total=total_size, unit="B", unit_scale=True, desc=filename) as pbar:
                async with session.get(url, timeout=timeout) as response:
                    if response.status != 200:
                        raise Exception(f"❌ GET failed with status {response.status}")

                    with open(filepath, "wb") as file:
                        async for chunk in response.content.iter_chunked(8192):
                            file.write(chunk)
                            pbar.update(len(chunk))

            logging.info(f"✅ Complete download: {filepath}")
            return filepath

        except (asyncio.TimeoutError, ClientError, Exception) as e:
            logging.warning(f"⚠️ Error in {attempt} when downloading {filename}: {e}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            else:
                logging.error(f"❌ All attempts to {filename} failed.")
                return None


async def monitor(devices):
    """Verifica periódicamente si hay nuevas versiones de IPSW y las descarga en paralelo."""
    
    print("  ___ ____  ______        __")
    print(" |_ _|  _ \/ ___\ \      / /")
    print("  | || |_) \___ \\ \ /\ / / ")
    print("  | ||  __/ ___) |\ V  V /  ")
    print(" |___|_|   |____/  \_/\_/   ")
    print("")                       
    print("      _                     _                 _           ")
    print("   __| | _____      ___ __ | | ___   __ _  __| | ___ _ __ ")
    print("  / _` |/ _ \ \ /\ / / '_ \| |/ _ \ / _` |/ _` |/ _ \ '__|")
    print(" | (_| | (_) \ V  V /| | | | | (_) | (_| | (_| |  __/ |   ")
    print("  \__,_|\___/ \_/\_/ |_| |_|_|\___/ \__,_|\__,_|\___|_|   ")
    print("")

    async with aiohttp.ClientSession() as session:
        while True:
            logging.info("🔍 Checking updates...")
            tasks = [get_latest_ipsw(session, device.strip()) for device in devices]
            results = await asyncio.gather(*tasks)

            for result in results:
                if result:
                    device_name = result["device"]
                    identifier = result["identifier"]
                    new_version = result["version"]
                    ipsw_url = result["url"]

                    # Verifica si ya tienes la última versión descargada
                    filename = f"{identifier}_{new_version}.ipsw"
                    filepath = os.path.join(DOWNLOAD_DIR, filename)

                    if os.path.exists(filepath):
                        logging.info(f"📦 You already have the latest version downloaded for {device_name} ({new_version}).")
                    else:
                        logging.info(f"🚨 New version available for {identifier}!")
                        logging.info(f"🔹 New version: {new_version}")
                        logging.info(f"🔗 URL: {ipsw_url}")

                        # Agrega la descarga a la lista de tareas asíncronas
                        await download_ipsw(session, identifier, new_version, ipsw_url)

            logging.info(f"⌛ Waiting {DEFAULT_INTERVAL // 60} minutes before the next verification...")
            await asyncio.sleep(DEFAULT_INTERVAL)

if __name__ == "__main__":
    fire.Fire({"monitor": lambda: asyncio.run(monitor(DEVICES.trim().split(" ")))})