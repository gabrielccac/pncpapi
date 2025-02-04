from fastapi import FastAPI
from seleniumbase import Driver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from contextlib import asynccontextmanager
import threading
import time

# Variáveis globais para gerenciar o driver, lock e último uso
driver = None
driver_lock = threading.Lock()
last_used_time = None
TIMEOUT = 300  # 5 minutos de inatividade

@asynccontextmanager
async def lifespan(app: FastAPI):
    global driver, last_used_time
    driver = None
    last_used_time = time.time()
    yield
    if driver:
        driver.quit()

app = FastAPI(lifespan=lifespan)

def wait_for_hcaptcha_ready():
    """Espera até que o hCaptcha esteja totalmente carregado e pronto"""
    wait = WebDriverWait(driver, 15)
    
    # Espera pelo iframe do hCaptcha
    iframe = wait.until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, 'iframe[data-hcaptcha-widget-id]')
    ))
    
    # Espera até que o objeto hcaptcha esteja disponível no JavaScript
    wait.until(lambda d: d.execute_script(
        "return typeof hcaptcha !== 'undefined' && hcaptcha.getResponse !== undefined"
    ))
    
    # Pequena pausa adicional para garantir que o hCaptcha está totalmente inicializado
    time.sleep(1)

def initialize_driver():
    global driver, last_used_time
    try:
        driver = Driver(uc=True, headless=True)
        driver.get("https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/public/landing?destino=acompanhamento-compra&compra=15695605900832024")
        
        # Espera pelo carregamento completo do hCaptcha
        wait_for_hcaptcha_ready()
        
    except Exception as e:
        print(f"Erro na inicialização: {str(e)}")
        if driver:
            driver.quit()
        driver = None
        raise

def close_driver_if_inactive():
    global driver, last_used_time
    if driver and (time.time() - last_used_time) > TIMEOUT:
        print("Fechando navegador por inatividade...")
        driver.quit()
        driver = None

@app.get("/get-token")
async def get_captcha_token():
    global driver, driver_lock, last_used_time
    
    with driver_lock:
        try:
            # Verifica inatividade
            close_driver_if_inactive()
            
            # Inicializa ou reinicializa o driver se necessário
            if not driver:
                print("Inicializando novo navegador...")
                initialize_driver()
            
            # Atualiza timestamp
            last_used_time = time.time()
            
            # Verifica se o hCaptcha ainda está pronto
            try:
                driver.execute_script("return typeof hcaptcha !== 'undefined'")
            except:
                print("hCaptcha não está pronto, reinicializando...")
                driver.quit()
                driver = None
                initialize_driver()
            
            js_function = """
            return new Promise((resolve) => {
                (async function() {
                    try {
                        const element = document.querySelector('[data-hcaptcha-widget-id]');
                        if (!element) {
                            resolve('');
                            return;
                        }
                        
                        const captchaId = element.getAttribute('data-hcaptcha-widget-id');
                        const response = await hcaptcha.execute(captchaId, {async: true});
                        resolve(response);
                    } catch(error) {
                        console.error('Erro:', error);
                        resolve('');
                    }
                })();
            });
            """
            
            # Executa o script com timeout explícito
            token = WebDriverWait(driver, 30).until(
                lambda d: d.execute_script(js_function)
            )
            
            # Reset do captcha
            driver.execute_script("""
                const element = document.querySelector('[data-hcaptcha-widget-id]');
                if (element && hcaptcha) {
                    hcaptcha.reset(element.getAttribute('data-hcaptcha-widget-id'));
                }
            """)
            
            return {"token": token or ""}
            
        except Exception as e:
            print(f"Erro na geração do token: {str(e)}")
            # Em caso de erro, força reinicialização na próxima chamada
            if driver:
                driver.quit()
                driver = None
            return {"token": ""}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)