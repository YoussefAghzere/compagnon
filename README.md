# Compagnon 0.1

Application Windows de capture et transcription locale des réunions et appels Teams en français, utilisable depuis une icône près de l’horloge.

## Utilisation

1. Lancer Compagnon, choisir le dossier des transcripts et le modèle Whisper (`base` par défaut).
2. Cocher **Capture automatique des appels Teams** et accepter l’avertissement. Le choix est mémorisé pour les prochains lancements, ainsi que le dossier, le modèle et le choix du microphone.
3. Cocher **Démarrer dans la zone de notification** pour les prochains lancements. Fermer la fenêtre avec sa croix ou cliquer **Masquer dans la zone de notification** : Compagnon continue à fonctionner.
4. Lancer un appel ou une réunion dans l’application Teams Windows. Aucun titre à saisir : la détection inspecte les boutons de fin d’appel accessibles, comme **Quitter**, **Raccrocher**, **Leave** ou **Hang up**. Le titre détecté sert à nommer le transcript.
5. Une notification et une icône rouge indiquent le démarrage de la capture. Après la fin de l’appel et 20 secondes sans bouton correspondant, la capture s’arrête et la transcription commence (icône orange). Une notification annonce la sauvegarde du TXT horodaté.

Clic droit sur l’icône : ouvrir les paramètres, activer/désactiver l’automatisation, démarrer manuellement, arrêter et transcrire, ouvrir les transcripts ou quitter. **Quitter Compagnon** ferme le processus ; pendant une capture/transcription, arrêter et attendre le résultat d’abord. Désactiver l’automatisation pendant une capture ne supprime pas celle-ci : utiliser **Arrêter et transcrire**.

Compagnon doit être lancé pour fonctionner. Cette version ne s’inscrit pas automatiquement au démarrage de Windows. L’icône peut être rangée dans les icônes masquées de Windows. Si elle ne peut pas être créée, la fenêtre reste accessible.

## Détection Teams : limites

- Application Teams **native Windows**, identifiée par `ms-teams.exe` ou `Teams.exe`. Teams dans un navigateur n’est pas pris en charge par l’automatisation.
- La détection est une inspection locale en lecture seule de l’interface Windows UI Automation, pas une API officielle Teams. Certaines versions, langues ou restrictions de l’entreprise peuvent empêcher l’accès aux boutons. Le bouton **Diagnostic Teams** affiche le dernier résultat ; le mode manuel reste disponible.
- Ouvrir simplement la fenêtre de discussion ou l’écran « Rejoindre » ne doit pas déclencher la capture. Aucun mot du titre n’est utilisé pour déclencher celle-ci.
- Une fenêtre d’appel déjà détectée peut être réduite sans arrêt de capture. Si Teams masque alors ses contrôles, Compagnon conserve l’état actif jusqu’à disparition/restauration de la fenêtre. Si un appel se termine dans une fenêtre réduite qui reste ouverte, l’arrêt peut nécessiter **Arrêter et transcrire** depuis l’icône.
- Une inspection en erreur ou bloquée n’est pas interprétée comme une fin d’appel. L’interface reste réactive et le diagnostic indique le problème. Une capture peut alors nécessiter un arrêt manuel.
- Deux appels sans intervalle d’absence de 20 secondes peuvent être regroupés dans une seule capture. La transcription d’une réunion occupe l’application ; une nouvelle réunion encore active sera capturée une fois le traitement terminé, mais son début peut manquer.
- Un arrêt manuel ne relance pas automatiquement la capture du même appel. Réactiver l’automatisation permet de réarmer la détection.

## Audio et confidentialité

La capture comprend tous les sons de la sortie Windows par défaut et, si activé, le microphone par défaut. Teams doit utiliser cette même sortie audio. Autoriser le microphone dans Windows. Un casque limite l’écho ; aucune annulation d’écho n’est implémentée. Éviter de changer de périphérique pendant la capture.

Informer les participants et respecter les règles de l’entreprise avant activation. Aucun audio, titre de fenêtre ou transcript n’est envoyé à un service de transcription distant. La transcription s’exécute sur CPU avec `faster-whisper` après l’arrêt ; le premier usage télécharge le modèle depuis Hugging Face, puis utilise le cache local. Un appel sans parole détectée affiche une erreur plutôt qu’un transcript vide.

Préférences et modèles : `%LOCALAPPDATA%\Compagnon`. Un WAV temporaire est écrit dans le dossier temporaire Windows puis supprimé après traitement, y compris en cas d’erreur normale. Un arrêt forcé peut laisser ce fichier ; la suppression n’est pas un effacement sécurisé. En cas d’échec de transcription, le WAV de capture n’est pas conservé.

## Développement Windows

Installer Python 3.12 avec Tcl/Tk, puis dans ce dossier :

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Pour mettre à jour une installation existante, fermer Compagnon via **Quitter Compagnon**, puis :

```powershell
git pull origin main
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Pour lancer sans console, utiliser `.\.venv\Scripts\pythonw.exe main.py`. Après configuration, le démarrage masqué est mémorisé. La fermeture de la console d’un lancement avec `python.exe` peut arrêter le processus : utiliser `pythonw.exe` ou la version portable pour le fonctionnement en arrière-plan.

## Application portable

Sur Windows : `powershell -ExecutionPolicy Bypass -File .\build.ps1`. Distribuer **tout le dossier** `dist\Compagnon`, puis lancer `Compagnon.exe`. Python n’est pas requis sur le PC destinataire. Les modèles ne sont pas inclus et nécessitent Internet au premier usage. L’exécutable n’est pas signé ; sa diffusion sur les PC professionnels peut nécessiter une validation informatique.

Le workflow GitHub Actions **Application Windows portable** construit ce dossier comme artefact après un push sur `main` ou un lancement manuel. Une ancienne version `.exe` doit être remplacée par un nouveau build pour bénéficier des corrections.

## Validation

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
```

Les tests couvrent l’export sans écrasement, le mixage simulé, le décodage réel d’un WAV avec PyAV, les contrôles d’appel, les transitions de début/fin et les commandes/états de l’icône. Les interfaces Windows UI Automation et la zone de notification sont simulées dans ces tests.

Avant distribution, vérifier **sur Windows** :

- Aucun démarrage sur l’écran de discussion ou avant de rejoindre un appel.
- Démarrage sur un appel nommé librement (par exemple `M3S - transcript test`) et voix locale/distante présentes dans le TXT.
- Capture poursuivie quand Compagnon est masqué et Teams réduit, arrêt automatique après disparition de la fenêtre d’appel.
- Menu de l’icône, notifications, démarrage masqué mémorisé, arrêt manuel sans redémarrage du même appel.
- Dossier portable sur un PC sans Python et import d’un enregistrement existant.

L’environnement de développement cloud est Linux : la capture WASAPI, les vrais contrôles Teams, la zone de notification Windows et le `.exe` n’y sont pas validés. Le téléchargement de modèle était bloqué par le proxy Hugging Face lors du premier essai ; aucune transcription réelle n’a été validée dans cet environnement.

## Compatibilité audio

`faster-whisper` 1.2.1 utilise `metadata_errors`, supprimé dans PyAV 19. `av==16.0.1` est fixé dans `requirements.txt` et le décodage est testé. Réinstaller les dépendances et relancer l’application après mise à jour.

## Suite envisagée

Compte rendu avec Qwen/Gemma, actions et décisions, historique, identification des intervenants, pause/reprise et politique de conservation. Ces fonctionnalités ne sont pas encore implémentées.
