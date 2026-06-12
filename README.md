# PhotoBeam — Transferència de fitxers mòbil → PC via WiFi

PhotoBeam és una eina lleugera que permet enviar fotos, vídeos i documents des del mòbil al PC sense cables, aplicacions de tercers ni núvol. Tot queda a la xarxa local.

---

## Com funciona

En executar l'script, s'obre automàticament una pàgina web al navegador del PC (**pantalla receptora**). Des del mòbil, s'obre una segona pàgina (**pantalla d'enviament**) escanejant el codi QR o escrivint la URL manualment.

Els fitxers enviats des del mòbil es desen automàticament a l'Escriptori del PC dins una carpeta amb la data del dia:

```
Escriptori/PhotoBeam 2026-06-11/
```

Cada sessió genera també un fitxer `_historial.txt` dins la mateixa carpeta amb el registre de tots els fitxers rebuts.

El servidor s'atura automàticament quan es tanca el navegador del PC.

---

## Requisits

- **Python 3.8** o superior
- Mòbil i PC connectats al **mateix WiFi**
- Llibreria `qrcode` (s'instal·la automàticament si no es troba)

---

## Instal·lació al Mac

### Opció 1 — Des del terminal (la més senzilla)

1. Desa `servidor_fotos.py` a l'Escriptori
2. Obre el Terminal (Aplicacions → Utilitats → Terminal)
3. Executa:

```bash
python3 ~/Desktop/servidor_fotos.py
```

El navegador s'obre sol. Per aturar el servidor, prem `Ctrl+C` al terminal.

---

### Opció 2 — Crear una aplicació amb Automator (doble clic)

Aquesta opció permet arrencar PhotoBeam fent doble clic a una icona, sense obrir el terminal.

**Pas 1.** Obre **Automator** (Aplicacions → Automator)

**Pas 2.** Tria **"Nova aplicació"** quan et pregunti el tipus de document

**Pas 3.** A la barra de cerca escriu `shell` i arrossega l'acció **"Executar script de shell"** a la columna de la dreta

**Pas 4.** Configura l'acció així:
- **Shell:** `/bin/bash`
- **Passa l'entrada:** `a stdin`
- **Contingut del script:**

```bash
cd ~/Desktop
python3 servidor_fotos.py
```

**Pas 5.** Desa amb **Cmd+S**:
- Format: **Aplicació**
- Nom: `PhotoBeam`
- Ubicació: Escriptori

**Pas 6.** La primera vegada cal fer **clic dret → Obrir** per passar la verificació de seguretat del Mac (Gatekeeper). Les vegades següents ja funciona amb doble clic normal.

> **Nota:** `servidor_fotos.py` ha d'estar sempre a l'Escriptori. Si el mous a una altra carpeta, cal actualitzar el `cd` del script de l'Automator.

---

### Opció 3 — Aplicació .app feta a mà

Si l'Automator dona problemes, es pot crear una `.app` manualment des del terminal:

```bash
# Crea l'estructura de l'aplicació
mkdir -p ~/Desktop/PhotoBeam.app/Contents/MacOS

# Crea el script executable
cat > ~/Desktop/PhotoBeam.app/Contents/MacOS/PhotoBeam << 'EOF'
#!/bin/bash
cd ~/Desktop
python3 servidor_fotos.py
EOF

# Fes-lo executable
chmod +x ~/Desktop/PhotoBeam.app/Contents/MacOS/PhotoBeam
```

Ara `PhotoBeam.app` apareix a l'Escriptori com una aplicació. La primera vegada, clic dret → Obrir.

---

## Instal·lació al Windows

### Opció 1 — Des del terminal

1. Instal·la Python 3 des de [python.org](https://www.python.org/downloads/) si no el tens
   - Durant la instal·lació, marca l'opció **"Add Python to PATH"**
2. Desa `servidor_fotos.py` a l'Escriptori
3. Obre el **Símbol del sistema** (busca `cmd` al menú Inici)
4. Executa:

```cmd
python %USERPROFILE%\Desktop\servidor_fotos.py
```

---

### Opció 2 — Doble clic amb un fitxer .bat

1. Crea un fitxer de text nou a l'Escriptori i anomena'l `PhotoBeam.bat`
2. Obre'l amb el Bloc de notes i enganxa:

```bat
@echo off
cd %USERPROFILE%\Desktop
python servidor_fotos.py
pause
```

3. Desa-ho i tanca el Bloc de notes
4. Doble clic a `PhotoBeam.bat` per arrencar el servidor

> La comanda `pause` fa que la finestra del terminal no es tanqui sola si hi ha algun error, permetent veure el missatge.

---

### Opció 3 — Accés directe sense terminal visible

Si prefereixes que no aparegui cap terminal en executar-ho:

1. Crea un fitxer `PhotoBeam.vbs` a l'Escriptori amb aquest contingut:

```vbscript
Set WShell = CreateObject("WScript.Shell")
WShell.Run "python " & WShell.ExpandEnvironmentStrings("%USERPROFILE%") & "\Desktop\servidor_fotos.py", 0, False
```

2. Doble clic a `PhotoBeam.vbs` per arrencar el servidor en segon pla

Per aturar-lo, obre el Gestor de tasques → busca el procés `python` → finalitza'l.

---

## Ús des del mòbil

1. Assegura't que el mòbil i el PC estan al **mateix WiFi**
2. Arrenca el servidor al PC (qualsevol de les opcions anteriors)
3. Al mòbil, obre la càmera i escaneja el **codi QR** que apareix a la pantalla del PC, o escriu manualment la URL que apareix (exemple: `http://192.168.1.42:8765/m`)
4. Toca **"Fotos i vídeos"** per seleccionar de la galeria, o **"Altres fitxers"** per enviar documents
5. Prem **"Enviar al PC →"**

Els fitxers apareixen immediatament a la pantalla del PC i es desen automàticament a la carpeta de destí.

---

## Estructura de la pantalla del PC

| Element | Descripció |
|---|---|
| URL per al mòbil | Adreça que cal obrir al mòbil |
| Codi QR | Escaneja per connectar el mòbil ràpidament |
| Carpeta de destí | On es desen els fitxers (Escriptori/PhotoBeam data/) |
| 📂 Obrir carpeta | Obre directament la carpeta al Finder/Explorador |
| 📋 Veure historial | Obre la carpeta on hi ha el fitxer `_historial.txt` |
| Filtres | Mostra Tot / Fotos / Vídeo / Documents |
| Comptadors | Total fitxers rebuts, fotos i MB |

---

## Solució de problemes

**El codi QR no apareix**
La primera vegada que s'executa, l'script instal·la automàticament la llibreria `qrcode`. Si no funciona, instal·la-la manualment:
```bash
pip3 install "qrcode[pil]"
```

**Error "Address already in use"**
El port 8765 ja està en ús (una sessió anterior no es va tancar bé). L'script intenta alliberar-lo automàticament. Si el problema persisteix, executa:
```bash
# Mac / Linux
lsof -ti :8765 | xargs kill -9

# Windows (cmd com a administrador)
for /f "tokens=5" %a in ('netstat -aon ^| find ":8765"') do taskkill /F /PID %a
```

**El mòbil no pot accedir a la URL**
- Verifica que mòbil i PC estan al **mateix WiFi** (no dades mòbils, no xarxes diferents)
- Comprova que el tallafoc del PC no bloqueja el port 8765
  - **Mac:** Preferències del Sistema → Seguretat → Tallafoc → Permet connexions entrants per a Python
  - **Windows:** Firewall de Windows → Permet una aplicació → Python

**Els fitxers no arriben**
- Mira els missatges al terminal: cada fitxer rebut correctament mostra `📸` o `📄` amb el nom i la mida
- Assegura't que la carpeta de destí (`Escriptori/PhotoBeam data/`) existeix i és accessible

---

## Notes tècniques

- El servidor corre al port **8765** per defecte (canviable a la variable `PORT` a l'inici de l'script)
- La carpeta de destí per defecte és `~/Desktop/PhotoBeam YYYY-MM-DD/`
- El servidor fa **polling** cada 1.5 segons per actualitzar la vista del PC en temps real
- Si el navegador del PC es tanca, el servidor s'atura automàticament al cap de **12 segons**
- No es necessita connexió a internet: tot funciona a la xarxa local
