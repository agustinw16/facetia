# Diagramas de Arquitectura — Chatbot Tesis

Este archivo contiene los diagramas del sistema en formato **Mermaid**, un lenguaje de texto que la mayoría de las herramientas de diagramas modernas soportan nativamente.

## Cómo usar estos diagramas

### Opción A — draw.io (recomendado)

1. Abrí https://app.diagrams.net/ (o draw.io en tu PC).
2. Menú **Arrange → Insert → Advanced → Mermaid...**
   (alternativa: **Extras → Edit Diagram → Mermaid**)
3. Copiá el bloque de código Mermaid (el contenido entre las ` ``` ` de cada sección, **sin la palabra `mermaid` ni los acentos graves**).
4. Pegalo en el cuadro y click **Insert**.
5. draw.io te lo renderiza como diagrama editable: podés mover cajas, cambiar colores y exportar como PNG/SVG/PDF para tu tesis.

### Opción B — Mermaid Live Editor (vista previa rápida)

1. Abrí https://mermaid.live/.
2. Pegá el código en el panel izquierdo.
3. Te lo renderiza en vivo a la derecha.
4. Botón "Actions → PNG/SVG" para descargarlo.

### Opción C — VS Code (vista previa local)

Instalá la extensión **"Markdown Preview Mermaid Support"** y al abrir este archivo con `Ctrl+Shift+V` ves todos los diagramas renderizados.

### Opción D — GitHub

Si pusheás este archivo a un repo público, GitHub renderiza los Mermaid automáticamente al verlo online.

---

## 1. Flujo COMPLETO — Recepción y respuesta de un mensaje (sistema final, Etapa 3+)

> Este es el flujo end-to-end con todos los componentes. **Ahora soporta Meta o Twilio** según la configuración de `WHATSAPP_PROVIDER`. El diagrama muestra "WhatsApp Provider" como abstracción.

```mermaid
flowchart TD
    U([Usuario en WhatsApp]) -->|1. envia mensaje| WA[WhatsApp App]
    WA -->|2. transmite| PROV{WHATSAPP_PROVIDER<br/>config}
    
    PROV -->|meta| META[Meta Cloud API]
    PROV -->|twilio| TWILIO[Twilio API]
    
    META -->|3. POST webhook| BACK[Tu Backend Flask<br/>en Render]
    TWILIO -->|3. POST webhook| BACK

    BACK -->|4. obtener_provider| PROVIDER["WhatsApp Provider<br/>(Meta o Twilio)<br/>del factory"]
    BACK -->|5. validar request| SIG{Firma valida?<br/>HMAC / Twilio sig}
    SIG -->|no| ERR[401 Unauthorized]
    SIG -->|si| DEDUP{Ya procesado<br/>este message_id?}

    DEDUP -->|si| OK200a[200 OK<br/>no procesa]
    DEDUP -->|no| RESP200[Responde 200<br/>inmediatamente]

    RESP200 -->|6. dispara en background| WORKER[Worker / thread<br/>de procesamiento]

    WORKER -->|7. guarda| DB[(PostgreSQL<br/>tabla mensajes)]
    WORKER -->|8. embebe pregunta| EMB[OpenAI<br/>text-embedding-3-small]
    EMB -->|vector 1536 dim| WORKER

    WORKER -->|9. busca top-K chunks| VDB[(Vector DB<br/>Qdrant / ChromaDB)]
    VDB -->|chunks relevantes| WORKER

    WORKER -->|10. pregunta + contexto| LLM[OpenAI GPT-4o-mini]
    LLM -->|respuesta natural| WORKER

    WORKER -->|11. provider.enviar_mensaje| PROVIDER
    PROVIDER -->|envia| ENVIO{Provider activo}
    ENVIO -->|meta| GRAPH[Graph API<br/>send message]
    ENVIO -->|twilio| TWILIO_SDK[Twilio SDK<br/>send message]
    
    GRAPH -->|transmite| META
    TWILIO_SDK -->|transmite| TWILIO
    
    META -->|12. transmite| WA
    TWILIO -->|12. transmite| WA
    WA -->|13. respuesta visible| U
    
    WORKER -->|14. guarda respuesta| DB

    style U fill:#e1f5ff
    style WA fill:#dcf8c6
    style META fill:#fff4e1
    style TWILIO fill:#fff4e1
    style BACK fill:#f0e1ff
    style PROVIDER fill:#f0e1ff
    style WORKER fill:#f0e1ff
    style DB fill:#ffe1e1
    style VDB fill:#ffe1e1
    style EMB fill:#e1ffe1
    style LLM fill:#e1ffe1
    style GRAPH fill:#fff4e1
    style TWILIO_SDK fill:#fff4e1
    style PROV fill:#fff9e1
```

---

## 2. Flujo ACTUAL — Recepción de un mensaje (Etapa 2, sin IA todavía)

> Es lo que tenés AHORA con la Etapa 2 funcionando. También soporta Meta o Twilio mediante el provider abstracto.

```mermaid
flowchart TD
    U([Usuario en WhatsApp]) -->|envia mensaje| WA[WhatsApp App]
    WA -->|transmite| PROV{WHATSAPP_PROVIDER}
    
    PROV -->|meta| META[Meta Cloud API]
    PROV -->|twilio| TWILIO[Twilio API]
    
    META -->|POST webhook| BACK[Backend Flask en Render]
    TWILIO -->|POST webhook| BACK

    BACK -->|obtener_provider| PROVIDER["WhatsApp Provider<br/>del factory"]
    BACK -->|provider.parsear| PARSE{Es mensaje<br/>de texto?}
    PARSE -->|no audio/imagen| IGN[200 OK<br/>ignora]
    PARSE -->|si| DEDUP{Ya procesado<br/>message_id?}

    DEDUP -->|si| DUP[200 OK<br/>no responde]
    DEDUP -->|no| FLOW[Continua flujo]

    FLOW -->|busca o crea| DB[(PostgreSQL<br/>tabla usuarios)]
    FLOW -->|guarda entrante| DB
    FLOW -->|arma ECO| ECHO[respuesta = 'Esta es la respuesta...']

    ECHO -->|provider.enviar_mensaje| PROVIDER
    PROVIDER -->|meta| GRAPH[Graph API send]
    PROVIDER -->|twilio| TSDK[Twilio SDK send]
    
    FLOW -->|guarda saliente| DB

    GRAPH --> META
    TSDK --> TWILIO
    META --> WA
    TWILIO --> WA
    WA --> U

    style U fill:#e1f5ff
    style WA fill:#dcf8c6
    style META fill:#fff4e1
    style TWILIO fill:#fff4e1
    style BACK fill:#f0e1ff
    style PROVIDER fill:#f0e1ff
    style FLOW fill:#f0e1ff
    style DB fill:#ffe1e1
    style GRAPH fill:#fff4e1
    style TSDK fill:#fff4e1
```

---

## 3. Ingesta de conocimiento (proceso OFFLINE que corrés vos)

> Este es el script `scripts/cargar_documentos.py` que vas a tener en la Etapa 3. NO se ejecuta automáticamente: vos lo corrés cuando agregás info nueva a la base de conocimiento.

```mermaid
flowchart LR
    A[Vos pones<br/>PDFs en data/raw/] --> B[python scripts/<br/>cargar_documentos.py]
    B --> C[Lee archivos PDF/MD/TXT]
    C --> D[Corta en chunks<br/>~500 tokens<br/>overlap 50]
    D --> E[Para cada chunk:<br/>OpenAI embeddings]
    E --> F[Vector<br/>1536 dim]
    F --> G[(Vector DB<br/>Qdrant/Chroma)]
    G -.->|listo para queries| H((Base de<br/>conocimiento<br/>disponible))

    style A fill:#e1f5ff
    style B fill:#f0e1ff
    style E fill:#e1ffe1
    style G fill:#ffe1e1
    style H fill:#dcf8c6
```

---

## 4. Arquitectura de componentes (vista de "cajas")

> Cómo se organizan los módulos del backend. **INCLUYE** la nueva carpeta `whatsapp/providers/` con el patrón Strategy que permite Meta o Twilio sin tocar el código.

```mermaid
flowchart TB
    subgraph EXT[Servicios externos]
        META_API[Meta Cloud API]
        TWILIO_API[Twilio API]
        OPENAI[OpenAI API<br/>embeddings + LLM]
        QDRANT[Qdrant Cloud<br/>Vector DB]
        PG[PostgreSQL<br/>en Render]
    end

    subgraph BACK[Backend Flask - Render]
        APP[app.py<br/>rutas HTTP]
        CONFIG[config.py<br/>WHATSAPP_PROVIDER<br/>+ variables]

        subgraph WSP[whatsapp/]
            WEBHOOK[webhook.py<br/>GENERICO - delega<br/>al provider activo]
            UTILS[utils.py<br/>formatear_numero]
            
            subgraph PROV[providers/<br/>STRATEGY PATTERN]
                BASE["base.py<br/>WhatsAppProvider<br/>interfaz abstracta"]
                META_IMPL["meta.py<br/>MetaProvider<br/>implementacion"]
                TWILIO_IMPL["twilio.py<br/>TwilioProvider<br/>implementacion"]
                FACTORY["__init__.py<br/>factory<br/>obtener_provider()"]
            end
        end

        subgraph CHAT[chatbot/]
            RAG[rag.py]
            EMBED[embeddings.py]
            VECDB[vector_db.py]
            LLM[llm.py]
        end

        subgraph DB[database/]
            CONN[connection.py]
            MODELS[models.py]
            REPO[repositorio.py]
        end
    end

    USR([Usuario]) -.WhatsApp.-> META_API
    USR -.WhatsApp.-> TWILIO_API

    META_API -->|POST webhook| APP
    TWILIO_API -->|POST webhook| APP

    APP --> CONFIG
    APP --> WEBHOOK

    WEBHOOK -->|obtener_provider| FACTORY
    FACTORY --> META_IMPL
    FACTORY --> TWILIO_IMPL
    META_IMPL --> BASE
    TWILIO_IMPL --> BASE

    WEBHOOK -->|delega a| PROV

    WEBHOOK --> RAG
    WEBHOOK --> REPO
    WEBHOOK --> UTILS

    META_IMPL -->|POST| META_API
    TWILIO_IMPL -->|SDK| TWILIO_API

    RAG --> EMBED
    RAG --> VECDB
    RAG --> LLM

    EMBED -->|API call| OPENAI
    LLM -->|API call| OPENAI
    VECDB -->|REST| QDRANT

    REPO --> CONN
    CONN -->|SQL| PG

    CONFIG --> META_IMPL
    CONFIG --> TWILIO_IMPL

    style EXT fill:#fff4e1
    style BACK fill:#f5f5f5
    style WSP fill:#f0e1ff
    style PROV fill:#e8d5ff
    style BASE fill:#d8c5ff
    style META_IMPL fill:#d8c5ff
    style TWILIO_IMPL fill:#d8c5ff
    style FACTORY fill:#d8c5ff
    style CHAT fill:#e1ffe1
    style DB fill:#ffe1e1
```

---

## 5. Secuencia detallada (vista temporal)

> Variante del diagrama 1 pero como **diagrama de secuencia**, mostrando el orden temporal explícito de cada llamada. Muy claro para defender la decisión de "responder 200 antes de procesar".

```mermaid
sequenceDiagram
    autonumber
    actor U as Usuario
    participant WA as WhatsApp
    participant PROV as WhatsApp<br/>Provider<br/>Meta o Twilio
    participant B as Backend Flask
    participant DB as PostgreSQL
    participant E as OpenAI Embed
    participant V as Vector DB
    participant L as GPT-4o-mini

    U->>WA: Escribe mensaje
    WA->>PROV: Transmite
    PROV->>B: POST /whatsapp (con firma)
    B->>B: Valida firma
    B->>DB: SELECT mensajes WHERE message_id=?
    DB-->>B: No existe
    B-->>PROV: 200 EVENT_RECEIVED
    Note over B: Procesa en background<br/>(thread / cola)
    B->>DB: INSERT usuario (si nuevo)
    B->>DB: INSERT mensaje entrante
    B->>E: POST /embeddings (pregunta)
    E-->>B: Vector 1536 dim
    B->>V: Search top-K similares
    V-->>B: 5 chunks relevantes
    B->>L: POST /chat/completions<br/>(system + chunks + pregunta)
    L-->>B: Respuesta natural
    B->>PROV: enviar_mensaje(numero, texto)
    PROV->>PROV: Meta API o Twilio SDK
    PROV-->>WA: Mensaje transmitido
    WA->>U: Muestra respuesta
    B->>DB: INSERT mensaje saliente
```

---

## 6. Arquitectura de Providers — Patrón Strategy

> Diagrama que explica específicamente cómo funciona el sistema multi-provider. Útil para defender en la tesis la decisión arquitectónica de desacoplamiento.

```mermaid
flowchart TD
    subgraph CLIENTE[Código cliente<br/>webhook.py]
        WEBHOOK["verificar_webhook()<br/>procesar_mensaje_entrante()"]
    end

    subgraph FACTORY[Factory<br/>providers/__init__.py]
        GET["obtener_provider()"]
        CONFIG["lee WHATSAPP_PROVIDER<br/>del .env / Render"]
    end

    subgraph INTERFAZ[Interfaz abstracta<br/>providers/base.py]
        BASE["WhatsAppProvider<br/>─────────────<br/>+ verificar_webhook()<br/>+ parsear_mensaje_entrante()<br/>+ enviar_mensaje()"]
    end

    subgraph IMPL[Implementaciones concretas]
        META["MetaProvider<br/>─────────────<br/>Meta Cloud API<br/>Graph API POST<br/>Hub.verify_token"]
        TWILIO["TwilioProvider<br/>─────────────<br/>Twilio SDK<br/>client.messages.create()<br/>form-encoded POST"]
    end

    subgraph EXTERNO[Servicios externos]
        META_EXT["Meta Cloud API<br/>graph.facebook.com"]
        TWILIO_EXT["Twilio API<br/>twilio.com"]
    end

    WEBHOOK -->|solicita| FACTORY
    FACTORY -->|read| CONFIG
    CONFIG -->|retorna meta| IMPL
    CONFIG -->|retorna twilio| IMPL

    FACTORY -->|instancia| INTERFAZ
    META -->|implementa| INTERFAZ
    TWILIO -->|implementa| INTERFAZ

    WEBHOOK -->|llama| INTERFAZ
    META -->|comunica con| META_EXT
    TWILIO -->|comunica con| TWILIO_EXT

    style CLIENTE fill:#f0e1ff
    style FACTORY fill:#f0e1ff
    style INTERFAZ fill:#e8d5ff
    style META fill:#d8c5ff
    style TWILIO fill:#d8c5ff
    style META_EXT fill:#fff4e1
    style TWILIO_EXT fill:#fff4e1
```

---

## Notas para la defensa

Cuando expliques estos diagramas en tu tesis, los puntos clave a destacar:

### General

1. **Separación entre "recibir" y "enviar"**: el webhook (proveedor → vos) y la API de envío (vos → proveedor) son dos canales distintos, no una conexión bidireccional.

2. **Por qué responder 200 antes de procesar**: el proveedor (Meta o Twilio) tiene timeout de ~10s. Si la IA tarda 5s + cold start de Render 30s, el proveedor da timeout y reintenta → mensajes duplicados. Responder 200 inmediatamente y procesar en background lo evita.

3. **Doble base de datos**: la **relacional** (Postgres) guarda usuarios y mensajes. La **vectorial** (Qdrant) guarda el conocimiento embebido. **No se sustituyen**, son complementarias.

4. **RAG vs. preguntar directo a la LLM**: el RAG (pasos 7-9) garantiza que el bot responda **solo con tu información real** y diga "no sé" cuando no tenga el dato, en vez de inventar. Es el aporte central de la tesis.

### Sobre el patrón Strategy (Diagrama 6)

5. **Por qué Strategy Pattern**: 
   - El código cliente (`webhook.py`) **NO sabe** si está usando Meta o Twilio.
   - Solo conoce una **interfaz abstracta** (`WhatsAppProvider`).
   - Cada proveedor implementa esa interfaz a su manera.
   - El **factory** decide cuál instanciar según configuración.

6. **Beneficio**: el administrador futuro del bot (ej: la facultad) puede cambiar de proveedor **sin tocar código**, solo modificando una variable de entorno (`WHATSAPP_PROVIDER`). Esto demuestra:
   - **Separación de responsabilidades**: cada módulo tiene un trabajo claro.
   - **Abierto para extensión, cerrado para modificación**: agregar un nuevo proveedor (ej: 360dialog) es crear un nuevo archivo, no modificar existentes.
   - **Inversión de dependencias**: el código de alto nivel depende de abstracciones, no de implementaciones concretas.

7. **Modularidad**: los diagramas 4 y 6 muestran que `whatsapp/`, `chatbot/` y `database/` son **cajas independientes**. Cambiar de Meta a Twilio afecta solo `whatsapp/providers/`, nada más.
