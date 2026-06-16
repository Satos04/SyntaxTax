# Documento de Contexto y Arquitectura: SyntaxTax

## 1. Visión General del Proyecto
**SyntaxTax** es un Micro-SaaS B2B (*Business-to-Business*) diseñado para cuantificar económicamente la deuda técnica de proyectos de software. Su objetivo principal no es actuar como un *linter* para desarrolladores, sino como una herramienta de auditoría financiera para CTOs, *Engineering Managers* e inversores.

El sistema analiza repositorios de código (comenzando por el ecosistema **Python**) extrae métricas de complejidad algorítmica y frecuencia de modificación, y traduce estos datos estáticos en métricas de coste financiero (ej. "dinero perdido al mes por mantenimiento de este archivo").

## 2. Decisiones de Stack Tecnológico
Para garantizar un despliegue ágil, de bajo coste y orientado a la escalabilidad en la nube, se han tomado las siguientes decisiones tecnológicas estrictas:

* **Lenguaje Principal:** Python 3.10+ (Motor de análisis y API).
* **Gestión de Entornos:** Uso exclusivo de `venv` nativo y `pip`. **Prohibido el uso de Anaconda/Conda** para asegurar un despliegue en servidor ligero y sin dependencias innecesarias propias del entorno académico de *Data Science*.
* **Framework API:** **FastAPI** (Elegido por su rendimiento asíncrono, autogeneración de documentación y soporte nativo de tipado estático `Pydantic`).
* **Base de Datos:** PostgreSQL, gestionada a través de **Supabase** (actuando también como posible proveedor de autenticación en fases posteriores).
* **Integración de Código:** **GitHub Apps** (Uso de Webhooks para eventos *Push*/*Pull Request* y GitHub API para extracción de código).
* **Frontend (Fase futura):** Ecosistema JavaScript/TypeScript (React/Next.js) o soluciones rápidas basadas en Python (Streamlit) para el *dashboard* de métricas.

## 3. Arquitectura del Monorepositorio
El proyecto sigue una arquitectura de monorepositorio estricta, separando la lógica de negocio pura de las interfaces de red. La regla de oro es que el motor de análisis no debe tener dependencias de red ni conocer la existencia de la API.

### Directorios Principales y Responsabilidades:

#### `core_analyzer/` (Motor Estático y Financiero)
Capa de lógica pura aislada. Recibe código fuente en texto y devuelve estructuras de datos financieras.
* **`parser.py`:** Utiliza la librería nativa `ast` (Abstract Syntax Tree) de Python. Su función es construir el árbol de nodos a partir del código fuente para su posterior análisis, evitando el uso de expresiones regulares frágiles.
* **`metrics.py`:** Recorre el árbol AST mediante algoritmos de grafos. Es el encargado de calcular la Complejidad Ciclomática de McCabe, además de otras métricas como duplicación o tamaño de bloque.
* **`financial_model.py`:** El núcleo de valor de negocio. Cruza las métricas de `metrics.py` con metadatos del control de versiones (frecuencia de *commits*, rotación de código) para estimar el impacto financiero real.

#### `api/` (Capa de Red y Webhooks)
Capa de infraestructura construida sobre FastAPI.
* **`main.py`:** Orquestador de la API. Expone los *endpoints* necesarios. Su función crítica es recibir los *payloads* de los Webhooks de GitHub, encolar el trabajo, llamar a `core_analyzer` y devolver respuestas HTTP 200 rápidas para evitar *timeouts* en GitHub.
* **`routes/`:** Controladores separados por dominio (ej. `/github/webhook`, `/dashboard/metrics`).
* **`database.py`:** Gestor de conexiones y operaciones CRUD con Supabase (PostgreSQL), almacenando el histórico de deuda por repositorio y cliente.

#### `dashboard/` (Capa de Presentación)
Directorio reservado para la interfaz gráfica de usuario. Consumirá la API para renderizar gráficos de evolución de deuda técnica, paneles de control para directivos y alertas de eficiencia.

#### Archivos de Configuración (Raíz)
* **`.env.example`:** Plantilla obligatoria que lista las variables de entorno necesarias (ej. `SUPABASE_URL`, `GITHUB_WEBHOOK_SECRET`) sin contener secretos reales.
* **`.gitignore`:** Configurado estrictamente para ocultar entornos virtuales (`.venv`), cachés (`__pycache__`) y variables de entorno (`.env`).

## 4. Flujo de Execución (Ciclo de Vida de un Análisis)
Cualquier agente de IA que trabaje en este proyecto debe respetar este flujo de datos:
1.  **Evento:** Un desarrollador realiza un *Push* en un repositorio cliente monitorizado.
2.  **Ingesta:** GitHub envía un Webhook JSON a `api/main.py`.
3.  **Extracción:** La API utiliza el token de la GitHub App para descargar únicamente los archivos `.py` modificados (o realiza un *shallow clone* efímero).
4.  **Procesamiento:** Los archivos se envían a `core_analyzer/parser.py` para generar el AST.
5.  **Cálculo:** `metrics.py` analiza el AST y `financial_model.py` le asigna un valor monetario a la penalización.
6.  **Persistencia:** La API guarda el delta de deuda técnica en la base de datos a través de `database.py`.
7.  **Notificación (Opcional):** Si la deuda supera el umbral, la API puede publicar un comentario automatizado en el *Pull Request* del cliente.

## 5. Directrices Estrictas de Desarrollo (AI Agent Rules)
* **Aislamiento de Dominios:** Nunca importar librerías de `api/` dentro de `core_analyzer/`. El motor debe poder ejecutarse localmente desde la terminal sin levantar el servidor web.
* **Tipado Estricto:** Es obligatorio el uso de *Type Hinting* en todas las firmas de funciones de Python (`def function(param: str) -> dict:`).
* **Modularidad sobre Optimización Prematura:** Escribir código legible y funciones puras antes de buscar micro-optimizaciones algorítmicas, salvo en el recorrido del AST donde la eficiencia en grafos grandes es crítica.
* **Seguridad:** Absolutamente ninguna credencial *hardcodeada*. Todo secreto debe inyectarse a través de `os.getenv()`.