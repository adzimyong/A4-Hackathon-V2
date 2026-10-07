# Ask Our Documents: User Manual

A fully local assistant that answers questions about government documents (policies, SOPs, circulars, meeting minutes) with cited sources.
Everything runs on your own laptop: no cloud, no API keys, no document ever leaves the machine.

**What it can do**

- Answer questions in English or Bahasa Malaysia, with the source file and page for every answer
- Show a library overview ("How many files are there?")
- Turn meeting minutes into an action-items table (owner, deadline) and download it as CSV
- Control who can see what: **Public**, **Staff** and **Manager** roles

---

## About the project

**The problem.** Government agencies keep thousands of documents: policies, SOPs, circulars, guidelines, reports and meeting minutes. Finding one answer means opening many files, and staff lose a lot of time searching.

**Our solution.** *Ask Our Documents* is a search assistant for these documents. An employee types a normal question, in English or Bahasa Malaysia, and gets a short answer with the exact source file and page, so they can check it.

**How it works (in simple words)**
1. The app reads every document (PDF, Word, text) and cuts it into small passages.
2. Each passage is turned into numbers that capture its meaning, and stored in a local database.
3. When someone asks a question, the app finds the most relevant passages. It combines search by meaning with search by exact keywords.
4. A small AI model writes the answer using only those passages, and cites them like [1] and [2].
5. If nothing relevant is found, the app says so and does not guess.

**Main features**
- **Cited answers:** every answer shows its sources and the passage it came from
- **Honest when unsure:** it says "I couldn't find it" instead of making up an answer
- **Access control:** Public, Staff and Manager roles. Documents are classified as public, internal or confidential, and each role only sees and searches what it is allowed to. Restricted topics show a 🔒 message
- **Library overview:** ask "How many files are there?" or browse files by folder
- **Meeting minutes to action items:** turns minutes into a table of decisions, tasks, owners and deadlines, which can be downloaded as CSV
- **Easy to add documents:** managers can upload files and choose who can see them

**Why it runs locally.** Government documents can be sensitive. Everything runs on the user's own computer, with no cloud service and no internet needed after setup, so no document ever leaves the machine.

**Built with:** Python, Streamlit (web interface), Ollama (runs the AI models on the laptop: `bge-m3` for search and `llama3.2:3b` for answers), ChromaDB (local database) and BM25 keyword search.

**Possible next steps:** connect to open government data portals such as data.gov.my, add more file types and scanned documents (OCR), add real user login instead of the demo roles, and use a larger model on a stronger machine for better answers.

---

## Team
- Mohamad Adzim Yong BIN MOHD. SHAHRIL
- Siti Hasya BINTI MOHAMMAD APPANDI
- Aisya BINTI ABU HASSAN ALSHAARI
- Evelyn Ann ANAK KENEDY
- Megan Nacha SENGALANG

---

**Download:** on the GitHub page click the green **Code** button, then **Download ZIP**, and follow the steps below.

---

## 1. What you need
- A Windows laptop with **8 GB RAM or more** (16 GB is better) and about **6 GB free disk space**
- Internet for the first-time setup only (to download Python packages and the AI models)
- About 20 to 30 minutes for the first setup

## 2. Step by step setup (Windows + VS Code)

### Step 1: Install Python (64-bit)
1. Go to https://www.python.org/downloads/windows/ and download **Python 3.11 or 3.12, "Windows installer (64-bit)"**.
   A 32-bit Python cannot install the database library (chromadb), so do not pick the 32-bit installer.
2. Run the installer. **Tick "Add python.exe to PATH"** on the first screen, then click Install Now.
3. Open a new PowerShell window and check: `python --version` (it should print a version number).
4. Check it is 64-bit: `python -c "import struct; print(struct.calcsize('P')*8)"` must print **64**.
   If it prints 32, uninstall that Python (Settings > Apps) and install the 64-bit one.

### Step 2: Install Ollama (the local AI engine)
1. Go to https://ollama.com/download, download the Windows installer and run it.
2. Check in PowerShell: `ollama --version`
3. **Only if you get an "untrusted mount point" error** when pulling models (this happens on some laptops):
   ```
   mkdir C:\ollama_models
   setx OLLAMA_MODELS C:\ollama_models
   ```
   Then quit Ollama from the system tray (bottom right), open it again, and continue.

### Step 3: Download the two AI models
In PowerShell:
```
ollama pull bge-m3
ollama pull llama3.2:3b
```
This is about 2.5 GB in total. `bge-m3` reads and searches documents, `llama3.2:3b` writes the answers.

### Step 4: Get the project
1. Download the project ZIP (GitHub: **Code > Download ZIP**, or the link you were given).
2. Right-click the zip, choose **Extract All**, and extract it to a plain folder such as `C:\gov-docs-assistant` (if the zip makes a folder inside a folder, open the inner one that contains `app.py`).
   Avoid OneDrive or Desktop folders that sync, because syncing can lock the database files.
3. Open **VS Code**, choose **File > Open Folder**, and pick the extracted `gov-docs-assistant` folder.
4. Open a terminal inside VS Code: **Terminal > New Terminal**.

### Step 5: Install the Python libraries (one time)
```
python -m pip install -r requirements.txt
```
This can take a few minutes. A "pip notice: new release available" message is harmless.

If you see **"No module named pip"**, try these in order (stop when one works):
1. `python -m ensurepip --upgrade`, then run the install command again.
2. `py -m pip install -r requirements.txt` (the `py` launcher often finds the right Python).
3. Run `where python`. If the path contains `WindowsApps`, that is the Microsoft Store shortcut and not a real Python. Reinstall Python from python.org (tick "Add python.exe to PATH" and keep **pip** ticked under Customize installation), then open a new terminal.
4. In VS Code press Ctrl + Shift + P, type **Python: Select Interpreter**, and pick the Python you installed. Close and reopen the terminal.

### Step 6: Index the documents
```
python ingest.py
```
You should see it read the three sample documents and report the number of chunks. Run this again whenever you add files by hand to the `docs` folder.

### Step 7: Start the app
```
python -m streamlit run app.py
```
Your browser opens at **http://localhost:8501**. If it does not, open that address yourself.
To stop the app, click the terminal and press **Ctrl + C**.

> Shortcut: double-click `setup.bat` once (Steps 5 and 6 plus the model downloads), then double-click `run.bat` any time to start the app.

---

## 3. How to use it

**Roles (top of the left sidebar)**

| Role | Can see |
|---|---|
| Public | public documents only (circulars) |
| Staff | public + internal documents (SOPs) |
| Manager | everything, and can add or reclassify documents |

Each role has its own chat history. If you ask about a document your role cannot see, the app replies with a 🔒 message instead of the answer.

**Ask documents (default mode)**

Type a question at the bottom. The answer cites sources like [1]. Click **Sources** under an answer to see the exact passages.
The first question after starting is slower because the model is loading. After that it is faster.

**Library overview**

Ask "How many files are there?" or open **Library** in the sidebar to see every file by folder and access level.

**Action items (Mode: 📝 Action items)**

1. Pick a meeting-minutes document.
2. Click **Extract action items**. Minutes that use `ACTION:` and `DECISION:` labels are read instantly.
   For informal minutes, tick **Use the AI to read the whole document** (slower).
3. Use **✖ Cancel** if it takes too long. Download the table with **Download as CSV**.

**Add or reclassify documents (Manager only)**

- Sidebar > **Add a document**: upload a PDF, DOCX, TXT or MD file, choose its type and who can see it, then **Add & index**.
- **Change who can see a document** changes a file's level at any time.

**Adding your own files by hand**

Put files in `docs/<type>/` (for example `docs/sop/`), then run `python ingest.py` again or click **Re-index everything** as Manager.

---

## 4. Sample documents and demo questions
The `docs` folder contains three fictional sample documents (they say "SAMPLE DOCUMENT" in the footer).

| Role | Question | Expected answer |
|---|---|---|
| Public | What is the limit for direct purchase? | RM 20,000 |
| Public | When does Circular 3/2026 take effect? | 1 November 2026 |
| Public | Which circular does it replace? | Circular No. 5 of 2024 |
| Staff | How many days before must I apply for annual leave? | 7 working days |
| Staff | What should I do for emergency leave? | Inform within 2 hours |
| Staff | How many days of leave can be carried forward? | 5 days |
| Manager | What alert thresholds were agreed? | 3.5 metres (first warning), 4.2 metres (evacuation) |
| Manager | How many sensors have been installed? | 18 of the 30 |
| Manager | Who will publish the tender for the backup power units? | Siti Mariam |
| Public | What alert thresholds were agreed? | 🔒 restricted for the Public role |
| Any | How many files are there? | Count that depends on the role |

---

## 5. Troubleshooting
| Problem | Fix |
|---|---|
| `streamlit` is not recognized | Always start with `python -m streamlit run app.py` |
| No module named pip | See the box under Step 5 (`python -m ensurepip --upgrade`, or `py -m pip ...`, or reinstall Python with pip ticked) |
| chromadb will not install | Most often a 32-bit Python (Step 1, point 4). Install 64-bit Python 3.11 or 3.12. Then run `python -m pip install --upgrade pip` and try again |
| `python` is not recognized | Reinstall Python and tick "Add python.exe to PATH", then open a new terminal |
| Connection refused / cannot reach Ollama | Open the Ollama app (check the system tray), then try again |
| `model not found` | Run the two `ollama pull` commands from Step 3 |
| "untrusted mount point" when pulling | See Step 2, point 3 (set `OLLAMA_MODELS`) |
| First answer is very slow | Normal: the model is loading. Ask one warm-up question before a demo |
| Answers are slow every time | Close other heavy programs, lower "Passages to use" in the sidebar to 3 |
| App says "couldn't find anything relevant" for a question that should work | Rephrase, or set a wider limit: `set MAX_DISTANCE=0.75` then start the app in the same terminal |
| A new file is not found | Click **Re-index everything**, or run `python ingest.py` |
| Database errors or odd file-lock messages | Move the project out of OneDrive, or set `DB_DIR` to a folder like `C:\gov_db` |
| Port 8501 already in use | Add `--server.port 8502` to the run command |
| Start fresh | Delete the `db` folder, then run `python ingest.py` |

## 6. Sharing the project with others
1. Put `gov-docs-assistant.zip` on Google Drive, OneDrive, or Teams, and set the link to "Anyone with the link can view".
2. Send the link together with this manual. The other person follows Section 2 on their own laptop.
3. Each laptop needs its own Ollama and models; the models are not inside the zip.

## 7. Project files
- `app.py`: the web interface
- `rag.py`: reading, searching, access control, answering, action items
- `ingest.py`: builds the search index from the `docs` folder
- `docs/`: your documents (sample files included)
- `.streamlit/config.toml`: colours and theme
