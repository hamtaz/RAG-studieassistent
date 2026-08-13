Jeg er 3. års dataingeniørstudent med grunnleggende kodekunnskap. Jeg bygger et RAG-basert (Retrieval-Augmented Generation) studieassistent-prosjekt i Python, som senere skal bruke CosmosDB for vektorsøk og Azure AI Foundry for LLM-kall.

Dette er trinn 1: data og forberedelse. Hjelp meg med å:
1. Bestemme hvilken type tekstmateriale som egner seg best som kildedata (f.eks. emnebeskrivelser, egne notater, PDF-er)
2. Skrive Python-kode som deler opp tekstene i mindre biter ("chunking"), ca. 300-500 ord per bit, med litt overlapp mellom bitene
3. Forklare hvorfor chunking gjøres på denne måten og hvilke fallgruver jeg bør unngå (for store/små biter, kutt midt i setninger, osv.)

Forklar konseptene underveis, ikke bare gi meg kode - jeg vil forstå hvorfor.

Jeg er 3. års dataingeniørstudent og bygger et RAG-basert studieassistent-prosjekt i Python. Jeg har allerede delt opp kildetekstene mine i mindre biter (chunking er ferdig). Neste steg er embeddings og lagring i CosmosDB.

Dette er trinn 2: embeddings og CosmosDB. Hjelp meg med å:
1. Forstå hva embeddings er og hvordan de brukes til vektorsøk (konseptuelt, med en enkel analogi)
2. Sette opp en Azure CosmosDB-instans med NoSQL API og vector search-funksjonalitet (jeg har Azure for Students-tilgang)
3. Skrive Python-kode som genererer embeddings av tekstbitene mine og lagrer dem i CosmosDB
4. Teste at et vektorsøk faktisk finner de mest relevante tekstbitene for et gitt spørsmål

Jeg har grunnleggende Python-kunnskap men har ikke jobbet med vektordatabaser eller embeddings før, så forklar underveis.

Jeg er 3. års dataingeniørstudent og bygger et RAG-basert studieassistent-prosjekt i Python. Jeg har CosmosDB satt opp med embeddings og fungerende vektorsøk. Neste steg er å koble på en språkmodell via Azure AI Foundry.

Dette er trinn 3: Azure AI Foundry og LLM-kall. Hjelp meg med å:
1. Sette opp en modell (f.eks. GPT-4o mini eller tilsvarende) i Azure AI Foundry
2. Skrive Python-kode som tar imot et brukerspørsmål, henter relevant kontekst (jeg har allerede vektorsøk mot CosmosDB), setter sammen en prompt med spørsmål + kontekst, og sender den til modellen i Foundry
3. Forklare god praksis for prompt-engineering i en RAG-kontekst, f.eks. hvordan jeg strukturerer prompten slik at modellen faktisk bruker konteksten jeg gir den

Forklar konseptene underveis - jeg har ikke jobbet med Azure AI Foundry før.

Jeg er 3. års dataingeniørstudent og bygger et RAG-basert studieassistent-prosjekt i Python med Azure AI Foundry og CosmosDB. RAG-pipelinen fungerer (henter kontekst og genererer svar). Nå vil jeg legge til sikkerhetsmekanismer, siden dette er et punkt jeg vil vise frem i jobbsøknader.

Dette er trinn 4: sikker AI-bruk. Hjelp meg med å:
1. Forstå hvilke sikkerhetsrisikoer som er relevante for en RAG-applikasjon (prompt injection, at modellen finner på ting utenfor kildematerialet, upassende input/output)
2. Sette opp Azure AI Content Safety for å filtrere input og output
3. Skrive en system-prompt som får modellen til å holde seg til kildematerialet og si fra når den ikke vet svaret, i stedet for å finne på noe
4. Lage noen enkle testcases for å sjekke at applikasjonen håndterer forsøk på prompt injection på en fornuftig måte

Forklar begrunnelsen bak hver sikkerhetsmekanisme, ikke bare implementasjonen.

Jeg er 3. års dataingeniørstudent og bygger et RAG-basert studieassistent-prosjekt i Python. Jeg har en fungerende RAG-pipeline (CosmosDB-vektorsøk + Azure AI Foundry-kall) med grunnleggende sikkerhetsfiltrering på plass. Nå vil jeg pakke alt inn i et ordentlig API.

Dette er trinn 5: samle det i et API. Hjelp meg med å:
1. Strukturere prosjektet som et FastAPI-prosjekt med god mappestruktur
2. Lage ett endepunkt som tar imot et spørsmål og returnerer svar + hvilke kilder (tekstbiter) svaret er basert på
3. Sette opp grunnleggende feilhåndtering og logging
4. Teste API-et lokalt

Jeg har grunnleggende Python-kunnskap men har ikke bygget et API med FastAPI før, så forklar konseptene underveis.

Jeg er 3. års dataingeniørstudent og bygger et RAG-basert studieassistent-prosjekt i Python. Jeg har et fungerende FastAPI-endepunkt som tar imot spørsmål og returnerer RAG-baserte svar. Nå vil jeg eksponere denne funksjonaliteten via Model Context Protocol (MCP), slik at studieassistenten kan brukes som et verktøy fra MCP-klienter som Claude Desktop.

Dette er trinn 6: MCP-eksponering. Hjelp meg med å:
1. Forstå hva MCP er og hvordan en MCP-server er strukturert (konseptuelt)
2. Skrive en enkel MCP-server-wrapper i Python rundt det eksisterende API-et mitt, som eksponerer "still spørsmål til studieassistenten" som et tool
3. Teste MCP-serveren lokalt, f.eks. med Claude Desktop

Jeg har ikke jobbet med MCP før, så forklar protokollen og konseptene underveis, ikke bare gi meg kode.

Jeg er 3. års dataingeniørstudent og har bygget et RAG-basert studieassistent-prosjekt: Python-backend med FastAPI, vektorsøk i CosmosDB, LLM-kall via Azure AI Foundry, sikkerhetsfiltrering, og MCP-eksponering. Nå vil jeg deploye det og dokumentere det ordentlig, siden dette skal vise frem i jobbsøknader og på GitHub.

Dette er trinn 7: deploy og dokumenter. Hjelp meg med å:
1. Deploye FastAPI-applikasjonen på Azure App Service (steg for steg, jeg har ikke deployet noe til Azure før)
2. Sette opp nødvendige miljøvariabler/secrets på en sikker måte i produksjon
3. Skrive en god README med arkitekturbeskrivelse, teknologivalg og begrunnelse, som jeg kan bruke direkte i jobbsøknader eller vise frem på GitHub-profilen min

Gi meg en README-struktur jeg kan fylle ut, i tillegg til deploy-stegene.