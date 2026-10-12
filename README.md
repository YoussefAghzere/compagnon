# Compagnon

MVP Windows de transcription locale des réunions Teams en français.

## Fonctionnalités disponibles

- Capture du son de la sortie Windows par défaut, avec microphone optionnel.
- Import d'un enregistrement audio existant.
- Transcription sur CPU avec faster-whisper (modèles tiny/base/small/medium).
- Export TXT horodaté dans un dossier configurable, sans écraser les exports précédents.
- Détection Teams expérimentale, désactivée par défaut et réactivée explicitement à chaque lancement.

La transcription commence **après l'arrêt** de la capture. Le premier usage télécharge le modèle depuis Hugging Face ; les suivants utilisent le cache local. Aucun service de transcription distant n'est appelé.

## Développement sous Windows

Installer Python 3.12 (avec Tcl/Tk), puis dans ce dossier :

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Teams doit utiliser la même sortie audio que la sortie Windows par défaut. Autoriser l'accès au microphone dans Windows. Le casque est recommandé pour limiter l'écho ; la capture du micro et du son du PC n'effectue pas d'annulation d'écho. Ne pas changer de périphérique pendant la capture.

## Application portable

Sur **Windows**, exécuter `powershell -ExecutionPolicy Bypass -File .\build.ps1`. Distribuer **tout le dossier** `dist\Compagnon`, puis lancer `Compagnon.exe`. Python n'est pas nécessaire sur le PC destinataire. Les modèles ne sont pas inclus dans le dossier portable et nécessitent Internet au premier usage. L'exécutable n'est pas signé ; sa diffusion sur les PC professionnels peut nécessiter une validation informatique.

Les préférences et modèles sont stockés dans `%LOCALAPPDATA%\Compagnon`. Un WAV temporaire est écrit dans le dossier temporaire Windows puis supprimé après traitement, même en cas d'erreur normale. Un arrêt forcé peut laisser ce fichier ; la suppression n'est pas un effacement sécurisé. En cas d'échec de transcription, réessayer avec l'enregistrement original via l'import : le WAV temporaire de capture n'est pas conservé.

## Détection automatique : limites

La détection observe les titres des fenêtres visibles contenant « Teams » et « réunion », « meeting », « appel » ou « call ». Ce n'est pas une intégration officielle Teams : certains titres ne seront pas détectés et certains écrans pourront déclencher une capture à tort. L'arrêt automatique intervient après 20 secondes sans fenêtre correspondante. Le mode manuel est le mode fiable du MVP. La capture inclut tous les sons passant par la sortie Windows, pas uniquement Teams. Informer les participants et respecter les règles de l'entreprise avant activation.

## Validation

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Test fonctionnel Windows requis avant distribution : lancer Teams avec un casque, démarrer la capture manuelle, faire parler un participant distant et le micro local, arrêter, puis vérifier que le TXT contient les deux voix. Tester également l'import, la fermeture après traitement et le dossier portable sur un PC sans Python. La capture WASAPI, l'interface Windows, l'autodétection Teams et la compilation `.exe` ne peuvent pas être validées sur une machine Linux.

## Suite envisagée

Compte rendu avec Qwen/Gemma, actions et décisions, historique, identification des intervenants, pause/reprise, icône près de l'horloge et politique de conservation. Ces fonctionnalités ne sont pas encore implémentées.

Le workflow GitHub Actions `Application Windows portable` produit également le dossier portable comme artefact après un push sur `main` ou un lancement manuel. Ce workflow est fourni, mais n'a pas été exécuté depuis cet environnement.

Validation effectuée dans l'environnement Linux : installation des dépendances, `pip check`, tests d'export, de mixage audio avec périphériques simulés et de décodage/rééchantillonnage réel avec PyAV. Le téléchargement du modèle a échoué avec une réponse proxy `403 Forbidden` vers Hugging Face ; aucune transcription réelle n'a donc été validée ici.

## Erreur `metadata_errors`

`faster-whisper` 1.2.1 utilise un argument supprimé dans PyAV 19. Le projet fixe donc `av==16.0.1`. Pour corriger une installation existante, récupérer le dernier code puis exécuter :

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Fermer puis relancer l'application. Pour la version portable, reconstruire avec `build.ps1` ou récupérer un nouvel artefact GitHub Actions ; modifier les dépendances Python locales ne corrige pas un ancien `.exe`.
