# Compagnon 0.2

Application Windows de transcription locale des réunions Teams : une configuration initiale, puis une icône près de l’horloge.

## Installer et configurer une fois

1. Télécharger **Compagnon.exe** (artefact GitHub Actions) et l’ouvrir. Ce fichier seul peut être partagé : Python et un dossier de DLL ne sont pas requis sur le PC destinataire.
2. Dans **Configuration**, choisir le dossier des transcripts et le modèle Whisper. `base` est le compromis par défaut ; `tiny` est plus rapide, `small`/`medium` plus précis mais plus lents.
3. Activer la capture automatique après avoir informé les participants. Choisir le microphone et le démarrage à l’ouverture de session Windows.
4. Cliquer **Enregistrer et activer**, puis masquer la fenêtre. Les préférences sont conservées.

L’ouverture manuelle montre **toujours** la fenêtre. Le démarrage masqué ne concerne que le lancement automatique Windows (`--background`), après configuration. Relancer le fichier pendant que Compagnon fonctionne rouvre la fenêtre existante ; aucune seconde capture parallèle n’est créée. La croix masque l’application, et **Quitter** l’arrête.

La première ouverture de v0.2 conserve le dossier et le modèle de v0.1 mais demande de valider la nouvelle configuration. Une ancienne préférence « masquer » ne ferme plus immédiatement l’écran de configuration.

## Démarrage Windows

Si cette option est cochée et enregistrée, la version `.exe` se copie dans **`%LOCALAPPDATA%\Compagnon\App\Compagnon.exe`** et ajoute une entrée utilisateur `Compagnon` dans **`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`**. Aucun droit administrateur n’est demandé. Elle se lance à l’ouverture de la session utilisateur, et non avant la connexion ni comme service Windows.

Le fichier téléchargé peut ensuite être déplacé : l’entrée pointe vers la copie installée. Avec le mode **Masquer au démarrage automatique**, seule l’icône apparaît. Si l’icône ne peut pas démarrer, la fenêtre est restaurée. Windows peut ranger l’icône dans les icônes masquées.

Pour désactiver le démarrage : décocher l’option et cliquer **Enregistrer et activer**. Pour retirer l’application : désactiver le démarrage, quitter via l’icône, puis supprimer le dossier `%LOCALAPPDATA%\Compagnon` si les réglages et modèles ne sont plus nécessaires. Les transcripts du dossier choisi ne sont pas supprimés.

Pour mettre à jour la copie installée : quitter l’ancienne instance via son icône, ouvrir le nouveau `.exe`, puis **Enregistrer et activer** avec le démarrage Windows coché. Ne pas tenter de remplacer l’exécutable pendant qu’il tourne. L’entreprise peut bloquer les exécutables non signés ou le démarrage utilisateur : demander alors une installation prise en charge par l’équipe informatique.

## Usage quotidien

Le tableau de bord affiche la capture, la transcription et la détection. Le menu de l’icône permet d’ouvrir les paramètres, de démarrer/arrêter manuellement, d’activer/désactiver l’automatisation et d’ouvrir les transcripts.

- **Bleu** : prêt ; **rouge** : capture ; **orange** : traitement.
- Démarrage automatique sur les boutons de fin d’appel Teams, sans saisie du titre.
- Après 20 secondes sans appel détecté : arrêt puis transcription sur CPU et export TXT horodaté, sans écraser les fichiers précédents.
- Notifications au début et à la fin. Les notifications Windows peuvent être désactivées ; l’icône et le tableau de bord restent les indicateurs disponibles.
- Import d’un fichier audio et capture manuelle disponibles en secours.

La capture automatique est expérimentale et nécessite une validation sur la version de Teams du poste. La capture du son reste active si l’automatisation est décochée pendant une réunion : utiliser **Arrêter et transcrire**. Quitter pendant un traitement nécessite d’arrêter et d’attendre le résultat.

## Limites de détection

Teams **natif Windows**, identifié par `ms-teams.exe` ou `Teams.exe`, est pris en charge ; Teams dans le navigateur ne l’est pas. L’application inspecte localement l’interface Windows UI Automation et cherche les boutons **Quitter**, **Raccrocher**, **Leave**, **Hang up** ou leurs identifiants. Il ne s’agit pas d’une API officielle Teams.

L’écran de discussion ou « Rejoindre » ne déclenche pas la capture. Les versions, langues et restrictions du poste peuvent toutefois empêcher l’accès aux boutons. **Diagnostic Teams** affiche et copie les contrôles accessibles, leurs noms/identifiants et leurs états. Le diagnostic est local ; relire son contenu avant de le partager, car il peut contenir des titres ou noms affichés par Teams.

Une fenêtre d’appel déjà détectée peut être réduite sans arrêt. Si ses contrôles deviennent inaccessibles, l’état actif est conservé jusqu’à restauration/disparition de la fenêtre. Une fin d’appel laissant cette fenêtre réduite ouverte peut nécessiter un arrêt manuel. Une inspection bloquée ou en erreur ne déclenche pas un arrêt : le diagnostic le signale et la fenêtre reste utilisable.

Deux appels sans intervalle d’absence de 20 secondes peuvent être regroupés. Une transcription occupe l’application ; une nouvelle réunion sera capturée quand le traitement finit si elle est encore active, mais son début peut manquer. Après un arrêt manuel, le même appel n’est pas automatiquement recapturé.

## Audio, modèles et stockage

La capture comprend **tous les sons de la sortie Windows par défaut** et le microphone par défaut s’il est activé. Teams doit utiliser cette même sortie. Autoriser le microphone dans Windows et utiliser un casque pour limiter l’écho. Aucune annulation d’écho n’est implémentée ; éviter de changer de périphérique pendant une capture.

Le premier usage télécharge le modèle depuis Hugging Face, puis utilise le cache local. **Le modèle n’est pas dans le `.exe`** : Internet est requis pour ce téléchargement, et les modèles peuvent occuper de plusieurs dizaines de Mo à plus d’un Go selon le choix. Aucun audio ni transcript n’est envoyé à un service de transcription distant. Un appel sans parole affiche une erreur plutôt qu’un transcript vide.

Préférences, application installée et modèles : `%LOCALAPPDATA%\Compagnon`. Un WAV temporaire est supprimé après traitement, même en cas d’erreur normale. Un arrêt forcé peut le laisser ; la suppression n’est pas un effacement sécurisé. En cas d’échec, l’audio temporaire de capture n’est pas conservé.

## Compiler et développer

Python Windows 3.11 à 3.13 est accepté ; Python 3.12 est utilisé en CI. Avec Tcl/Tk installé :

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Pour mettre à jour le code, quitter l’application puis :

```powershell
git pull origin main
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\build.ps1
```

Le script réutilise le `.venv` Windows existant. Sinon il cherche un Python compatible dans PATH ou via `py`, sans remplacer un environnement incompatible.

- **`build.ps1`** : produit `dist\Compagnon.exe`, fichier unique PyInstaller compressé, et affiche sa taille réelle.
- **`build.ps1 -Folder`** : variante `dist\Compagnon\Compagnon.exe` pour diagnostiquer le bundle ; distribuer alors tout ce dossier.
- Le fichier unique extrait son runtime dans un dossier temporaire au lancement : le premier démarrage peut être plus lent et son occupation décompressée reste plus importante que la taille du téléchargement.
- La collecte de fichiers de Whisper/CTranslate2 est ciblée au lieu de collecter tous leurs modules. Les dépendances natives restent lourdes : aucune taille Windows précise ni réduction garantie n’est annoncée avant compilation. Le modèle est téléchargé séparément.

Avec le code source, le démarrage utilisateur pointe vers `pythonw.exe` et le chemin absolu de `main.py`. Conserver cet environnement et ce checkout ; préférer le `.exe` pour la distribution.

Le workflow GitHub Actions **Application Windows portable** compile le fichier unique, exécute les tests, vérifie le runtime embarqué puis publie le `.exe` comme artefact téléchargeable. Il n’est pas signé.

## Validation et état réel

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
```

Les tests couvrent l’export, le mixage simulé, le décodage WAV réel avec PyAV, les règles et transitions d’appel, les commandes d’icône, la visibilité au lancement et l’enregistrement utilisateur avec un registre simulé. Le mode `--smoke-test chemin.json` vérifie les bibliothèques embarquées, le décodage et l’icône sans capturer, télécharger un modèle ou modifier le registre. Sur Windows il vérifie aussi le chargement de SoundCard, pystray et UI Automation.

Le cloud est Linux : les vrais appels Teams, la capture WASAPI, le registre Windows, l’activation d’une deuxième instance et le `.exe` nécessitent encore validation sur Windows. Le téléchargement de modèle était bloqué par le proxy lors du premier essai ; aucune transcription réelle n’a été validée ici.

Avant distribution : vérifier la configuration toujours accessible, le deuxième lancement, le démarrage après déconnexion/reconnexion Windows, l’arrêt du démarrage, le déplacement du fichier téléchargé, la capture avec deux voix et l’export, puis l’exécution du `.exe` seul sur un PC sans Python.

`av==16.0.1` évite l’incompatibilité `metadata_errors` entre faster-whisper 1.2.1 et PyAV 19.

## Prochaines améliorations

Préparation/vérification du modèle avant la première réunion, indicateur de niveau sonore, récupération d’audio après une erreur, historique consultable, compte rendu local avec actions et décisions, exécutable signé et mises à jour contrôlées. Ces fonctions ne sont pas encore implémentées.
