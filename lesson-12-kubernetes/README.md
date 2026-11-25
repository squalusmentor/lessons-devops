# Урок 12. Kubernetes

Compose управляет контейнерами на одной машине. Kubernetes управляет контейнерами на группе машин: раскладывает их по серверам, перезапускает упавшие, держит нужное число копий

В уроке стек живого проекта из урока 10 (MongoDB, API на Go, Telegram-бот) переезжает из compose в кластер. Кластер локальный, на minikube, манифесты "ручные" без хелма, Swagger бэкенда открывается через Ingress

---

## 1. Установка

```bash
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube

curl -LO "https://dl.k8s.io/release/$(curl -Ls https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install kubectl /usr/local/bin/kubectl
```

| Программа | Что делает |
|---|---|
| `minikube` | создаёт и запускает локальный кластер |
| `kubectl` | клиент кластера, через него идут все действия |

На Windows урок проходит внутри WSL, того же, что в уроке 8, с Docker внутри. Нода minikube это Linux-контейнер, и команды урока написаны под bash. Под ноду minikube отводит до 3 ГБ памяти

```
$ minikube version
minikube version: v1.39.0
commit: 7a9f6a841470a207de8cf4bafcccee0969d8ba10

$ kubectl version --client
Client Version: v1.37.3
Kustomize Version: v5.8.1
```

---

## 2. Запуск кластера

```bash
minikube start --driver=docker --ports=127.0.0.1:8080:80
minikube addons enable ingress
```

| Часть | Что значит |
|---|---|
| `--driver=docker` | нода кластера работает как контейнер Docker |
| `--ports=127.0.0.1:8080:80` | порт 80 ноды открыт на своей машине как 8080, через него приходит трафик Ingress. Порты контейнера задаются при создании, поэтому флаг стоит в первом `start` |
| `addons enable ingress` | ставит в кластер ingress-nginx, программу, которая исполняет правила Ingress из раздела 7 |

```
$ kubectl get nodes
NAME       STATUS   ROLES           AGE   VERSION
minikube   Ready    control-plane   18m   v1.37.0

$ kubectl get pods -n ingress-nginx
NAME                                       READY   STATUS      RESTARTS   AGE
ingress-nginx-admission-create-rnqts       0/1     Completed   0          12m
ingress-nginx-admission-patch-bxdn6        0/1     Completed   0          12m
ingress-nginx-controller-d7cd8c989-7bhfd   1/1     Running     0          12m
```

Кластер готов, когда нода в `Ready`, а `ingress-nginx-controller` показывает `1/1`

### Freelens

Lens это графический клиент кластера. Компаниям с выручкой или инвестициями больше 10 млн долларов он доступен по платной лицензии с пробными 30 днями. Freelens это открытый форк с тем же интерфейсом, без лицензий и аккаунта. Ставится в Windows, из PowerShell:

```powershell
winget install Freelensapp.Freelens
```

Kubeconfig это файл доступа к кластеру: в нём записано, куда подключаться и от чьего имени. По нему работают `kubectl`, Freelens и любой другой клиент. `minikube start` создаёт его в `~/.kube/config`

| Часть kubeconfig | На какой вопрос отвечает |
|---|---|
| cluster | где кластер: адрес API и сертификат, по которому клиент убеждается, что API настоящий |
| user | кто подключается: сертификат с ключом или токен |
| context | какой cluster и какой user использовать сейчас. По контекстам `kubectl` переключается между кластерами |

По user кластер решает, что тебе разрешено. Файл от minikube даёт права администратора. Это такой же секрет, как SSH-ключ: у кого файл, у того и доступ, в git ему не место

Доступ к кластеру выгружается из WSL в папку пользователя Windows:

```bash
mkdir -p /mnt/c/Users/<имя>/.kube
kubectl config view --minify --flatten > /mnt/c/Users/<имя>/.kube/minikube.yaml
```

| Часть | Что делает |
|---|---|
| `config view` | печатает kubeconfig: адрес API кластера и сертификаты доступа |
| `--minify` | оставляет только текущий кластер |
| `--flatten` | встраивает сертификаты в файл. В исходном стоят пути внутри WSL, из Windows они не читаются |

Freelens сам читает папку `.kube`, кластер `minikube` появляется в каталоге. `minikube start` после остановки открывает API на новом порту (`32771` стал `32776`), поэтому файл выгружается заново той же командой

---

## 3. Из чего состоит кластер

Пока сервер один, всё решает человек с `docker compose`: где запустить, что поднять, по какому адресу искать. Когда серверов десять, эту работу делят между собой части кластера. Сервер в кластере называется нодой: мастер-нода (control plane) принимает решения, на рабочих нодах (worker) крутятся контейнеры приложений

| Что нужно делать | На одном сервере | В кластере | Где встретишь |
|---|---|---|---|
| принимать команды | SSH и `docker compose` | kube-apiserver на мастере | к нему по kubeconfig ходят `kubectl` и Freelens |
| помнить, что должно работать | `docker-compose.yml` на диске | etcd на мастере, туда попадает каждый `kubectl apply` | бэкап кластера это бэкап etcd |
| выбрать сервер | тот, куда зашёл по SSH | kube-scheduler на мастере, по свободной памяти и CPU | под висит в `Pending`: места ни на одной ноде нет |
| держать нужное число копий | человек заметил и поднял | kube-controller-manager на мастере | удалённый под появляется снова |
| запустить контейнер, перезапустить упавший | Docker | kubelet на каждой ноде | статусы `ImagePullBackOff` и `CrashLoopBackOff` |
| найти сервис по имени | DNS docker-сети | CoreDNS и kube-proxy | `http://api:8080` ведёт в живой под, на какой бы ноде он ни был |

Кластер запускает поды. Под это обёртка над контейнером: свой IP, свои тома, обычно один контейнер внутри

Вместе это работает так. Ночью умирает нода, на которой жил api. kube-controller-manager видит, что копий меньше, чем в манифесте, и создаёт новый под. kube-scheduler выбирает ему живую ноду, её kubelet скачивает образ и запускает контейнер. Сервис возвращается за несколько минут сам, с compose в этом месте просыпается человек

Объекты кластера разложены по группам, namespace. `kubectl get pods` показывает группу `default`, в ней лежит приложение, а поды ingress-nginx видны с флагом `-n ingress-nginx`

---

## 4. Почему minikube не совсем кластер

Весь minikube это один контейнер Docker, в нём и мастер, и рабочая нода. Манифесты и команды те же, что в проде, но при падении этой ноды подам переезжать некуда

---

## 5. Образы

Кластер ничего не собирает, ключа `build` в манифестах нет: нода скачивает готовый образ из registry. Образы своего проекта лежат в Docker Hub с урока 7, пайплайн кладёт их туда по тегу

Образы примера публичные, `kot1gray/api:v0.3.10` и `kot1gray/telegram-bot:v0.2.14`. Их Dockerfile для чтения: [api](docker/api.Dockerfile) и [telegram-bot](docker/telegram-bot.Dockerfile)

| В Dockerfile | В манифесте |
|---|---|
| `EXPOSE 8080` у api | `containerPort: 8080`, и к этому порту нужен Service |
| у бота `EXPOSE` нет | Service не нужен: бот сам ходит в Telegram и в api, к нему никто не обращается |

---

## 6. Из compose в манифесты

Исходник: [docker-compose.yml](docker-compose.yml)

| В compose | В кластере |
|---|---|
| сервис | Deployment, в нём шаблон пода |
| имя сервиса в сети | Service с тем же именем. `mongodb://ec-mongodb:27017` и `http://api:8080` остались как были |
| `environment` | ConfigMap или `env` прямо в Deployment |
| `.env` | Secret |
| `volumes` | PersistentVolumeClaim (PVC) |
| `healthcheck` | `readinessProbe` |
| `mem_reservation`, `mem_limit`, `cpus` | `resources.requests` и `resources.limits` |
| `ports`, Caddy | Ingress |
| `restart: unless-stopped` | поведение по умолчанию |
| `networks` | нет, все поды видят друг друга |
| `depends_on` | нет, порядок запуска кластер не держит, раздел 8 |
| `${PORT:-8080}` | нет, значения пишутся сразу. Подстановки даёт Helm |

Единицы ресурсов другие:

| В compose | В манифесте |
|---|---|
| `cpus: 0.1` | `cpu: 100m`, тысячные доли ядра |
| `mem_limit: 128m` | `memory: 128Mi`. Запись `128m` здесь означает 0.128 байта, и API отклоняет манифест |

Из стека урока 10 переезжают `ec-mongodb`, `api` и `telegram-bot`. Остальное в урок не входит: Netdata смотрит на хост и контейнеры Docker, роль Caddy играет Ingress, а образ бэкапа собирается на VM и в registry не лежит, ноде его неоткуда скачать

---

## 7. Манифесты

Каждый объект начинается с одних и тех же полей:

| Поле | Что значит |
|---|---|
| `apiVersion`, `kind` | тип объекта |
| `metadata.name` | имя, уникальное для этого типа внутри namespace |
| `spec` | желаемое состояние |

### Secret

```bash
cp .env.example .env
kubectl create secret generic encon --from-env-file=.env
```

| Ключ | Значение |
|---|---|
| `BOT_TOKEN` | токен бота от BotFather в telegram |
| `POLZA_KEY`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` | заглушки из примера. api при старте проверяет, что они не пустые, для урока этого хватает |

Secret это пары «ключ и значение», которые лежат в самом кластере. Deployment ссылается на Secret по имени, поэтому один и тот же манифест работает с тестовым токеном в одном кластере и с боевым в другом

Secret создаётся командой, манифеста у него нет: файл с токеном оказался бы в git

```
$ kubectl describe secret encon
...
BOT_TOKEN:      46 bytes
POLZA_KEY:      4 bytes
S3_ACCESS_KEY:  4 bytes
S3_SECRET_KEY:  4 bytes

$ kubectl get secret encon -o jsonpath='{.data.POLZA_KEY}'
c3R1Yg==
```

| Что | Как устроено |
|---|---|
| хранение | в etcd, по умолчанию без шифрования. Base64 это кодировка, `base64 -d` возвращает исходное значение |
| `describe` | показывает имена ключей и размер, значение на экран не попадает |
| отличие от ConfigMap | хранят одно и то же, разделены ради доступа: настройки можно показать всей команде, токены единицам |
| передача в под | ключ становится переменной окружения через `secretKeyRef`, пример ниже у api |

Кому можно читать секреты, решает RBAC: роль перечисляет разрешённые действия с объектами, например «смотреть поды и логи, секреты закрыты», и выдаётся человеку или приложению. В minikube у тебя права администратора, поэтому открыто всё

### MongoDB

Файл [k8s/mongodb.yaml](k8s/mongodb.yaml), три объекта через `---`. Диск:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: ec-mongodb-data
spec:
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 1Gi
```

PVC это заявка на диск. Сам диск по заявке создаёт кластер, `ReadWriteOnce` подключает его к одной ноде

Deployment:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ec-mongodb
spec:
  replicas: 1
  # Две монги на одном каталоге данных не уживутся, поэтому старый под
  # останавливается до старта нового
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app: ec-mongodb
  template:
    metadata:
      labels:
        app: ec-mongodb
    spec:
      containers:
        - name: mongodb
          image: mongo:7.0
          args: [mongod, --quiet]
          ports:
            - containerPort: 27017
          volumeMounts:
            - name: data
              mountPath: /data/db
          readinessProbe:
            tcpSocket:
              port: 27017
          resources:
            requests:
              memory: 208Mi
            limits:
              memory: 512Mi
              cpu: 250m
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: ec-mongodb-data
```

Service:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: ec-mongodb
spec:
  selector:
    app: ec-mongodb
  ports:
    - port: 27017
```

| Часть | Что значит |
|---|---|
| `template` | шаблон пода, по нему создаётся каждая копия |
| `labels`, `matchLabels`, `selector` | метка `app: ec-mongodb` связывает объекты: по ней Deployment узнаёт свои поды, а Service находит, куда слать трафик |
| `volumes`, `volumeMounts` | под берёт диск по заявке, контейнер видит его в `/data/db` |
| `readinessProbe` | пока проба не прошла, Service не отправляет в под трафик |
| `requests` | сколько ресурсов зарезервировать, по этим числам планировщик выбирает ноду |
| `limits` | потолок, как `mem_limit` и `cpus`. Превышение памяти заканчивается OOM |
| Service | постоянное имя и адрес. У пода IP новый после каждого пересоздания |

В compose проба монги шла раз в 5 минут, потому что каждая запускала процесс внутри контейнера. `tcpSocket` выполняет kubelet снаружи, в лимиты монги проба не входит, и штатные 10 секунд ей не мешают

### api

Файл [k8s/api.yaml](k8s/api.yaml). Новое по сравнению с монгой: настройки из ConfigMap и токены из Secret

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: api
data:
  PORT: "8080"
  GIN_MODE: release
  ...
  MONGODB_URI: mongodb://ec-mongodb:27017
  ...
```

```yaml
          envFrom:
            - configMapRef:
                name: api
          env:
            # В .env ключ называется BOT_TOKEN, приложение ждёт другое имя
            - name: TELEGRAM_BOT_TOKEN
              valueFrom:
                secretKeyRef:
                  name: encon
                  key: BOT_TOKEN
          ...
          readinessProbe:
            httpGet:
              path: /health
              port: 8080
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            # До подключения к монге порт закрыт, ранний провал пробы
            # перезапускал бы под, который просто ждёт базу
            initialDelaySeconds: 60
```

| Часть | Что значит |
|---|---|
| `"8080"` в кавычках | ConfigMap хранит только строки, число без кавычек API отклоняет |
| `envFrom` | все ключи ConfigMap становятся переменными окружения |
| `secretKeyRef` | одна переменная из одного ключа. Бот так получает только `BOT_TOKEN`, ключи S3 ему не достаются |
| `readinessProbe` | при провале под убирается из Service и продолжает работать |
| `livenessProbe` | при провале контейнер перезапускается |

### telegram-bot

Файл [k8s/telegram-bot.yaml](k8s/telegram-bot.yaml): один Deployment без Service и без проб, порта у бота нет. `Recreate` здесь потому, что Telegram отдаёт сообщения одному получателю на токен, и два пода одновременно мешали бы друг другу

### Ingress

Точка входа трафика в кластер это ingress-контроллер: всё, что приходит снаружи, сначала попадает к нему. Манифест Ingress говорит контроллеру, какие запросы в какой Service передавать. В уроке 5 так же делились nginx и его `site.conf`: nginx принимал трафик, `location` и `proxy_pass` решали, куда он пойдёт

Контроллер один на весь кластер, Ingress у каждого приложения свой. Файл [k8s/ingress.yaml](k8s/ingress.yaml):

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api
spec:
  ingressClassName: nginx
  rules:
    - http:
        paths:
          # /metrics и /health сюда не входят, снаружи они не нужны
          - path: /docs
            pathType: Prefix
            backend:
              service:
                name: api
                port:
                  number: 8080
          - path: /api/v1
            pathType: Prefix
            backend:
              service:
                name: api
                port:
                  number: 8080
```

| Часть | Что значит |
|---|---|
| `ingressClassName` | какой контроллер исполняет правила |
| `path`, `pathType: Prefix` | всё, что начинается с этого пути, уходит в указанный Service |
| `host` отсутствует | правило действует для любого имени. В проде здесь домен |

Что контроллер делает по этому манифесту:

| Запрос | Куда уходит |
|---|---|
| `/docs/...` | Service `api`, порт 8080 |
| `/api/v1/...` | Service `api`, порт 8080 |
| остальное, например `/metrics` | правила нет, контроллер сам отвечает 404 |

```
браузер ──▶ localhost:8080 ──▶ нода :80 ──▶ ingress-контроллер ──▶ Service api ──▶ под api :8080
```

---

## 8. Запуск

```
$ kubectl apply -f k8s/
configmap/api created
deployment.apps/api created
service/api created
ingress.networking.k8s.io/api created
persistentvolumeclaim/ec-mongodb-data created
deployment.apps/ec-mongodb created
service/ec-mongodb created
deployment.apps/telegram-bot created
```

Через минуту:

```
$ kubectl get pods
NAME                            READY   STATUS    RESTARTS      AGE
api-5994d9c474-67qh6            1/1     Running   1 (12s ago)   69s
ec-mongodb-558d8f954b-gd4pl     1/1     Running   0             69s
telegram-bot-585fc8bb6f-87xfb   1/1     Running   0             69s

$ kubectl get svc,ingress,pvc
NAME                 TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)     AGE
service/api          ClusterIP   10.106.166.117   <none>        8080/TCP    4m46s
service/ec-mongodb   ClusterIP   10.109.132.200   <none>        27017/TCP   4m46s
service/kubernetes   ClusterIP   10.96.0.1        <none>        443/TCP     18m

NAME                            CLASS   HOSTS   ADDRESS        PORTS   AGE
ingress.networking.k8s.io/api   nginx   *       192.168.49.2   80      4m46s

NAME                                    STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
persistentvolumeclaim/ec-mongodb-data   Bound    pvc-4c25b464-9ec9-48fe-ace6-3c891e6191a2   1Gi        RWO            standard       <unset>                 4m46s
```

Имя пода складывается из трёх частей: `api` это Deployment, `5994d9c474` это версия его шаблона, `67qh6` это сам под

У api один рестарт. Он поднялся раньше монги, трижды не смог подключиться и завершился, kubelet запустил его снова:

```
$ kubectl logs deploy/api --previous --tail=1
2026/11/25 18:06:47 Failed to connect to MongoDB: failed to ping MongoDB after 3 attempts: ...
```

Так в кластере выглядит замена `depends_on`: приложение падает и перезапускается, пока зависимость не ответит

### Проверка

```
$ curl -s -o /dev/null -w "%{http_code}\n" localhost:8080/docs/index.html
200

$ curl -s -o /dev/null -w "%{http_code}\n" localhost:8080/metrics
404
```

Swagger открывается в браузере на `http://localhost:8080/docs/index.html`

Запрос статистики сделан с Telegram ID владельца проекта, список админов зашит в образ:

```
$ curl -s "localhost:8080/api/v1/admin/stats?admin_id=<ID админа>"
{"generated_at":"2026-11-25T18:07:08.153032847Z","total_users":1,"new_24h":1,"active_3d":{"total":1,"paid":0,"free":1},...}
```

База пустая, единственный пользователь это сам админ: api завёл его на этом запросе. Ответ означает, что прошёл весь путь, от Ingress через api до записи в монгу

### Что смотреть, когда под не готов

| `STATUS` | Что происходит | Где причина |
|---|---|---|
| `Pending` | нода не назначена: не хватает ресурсов или диск ещё не создан | `kubectl describe pod <под>`, блок `Events` внизу |
| `ContainerCreating` | скачивается образ | там же |
| `ErrImagePull`, `ImagePullBackOff` | образ не скачался | там же |
| `Running`, `READY 0/1` | процесс жив, readiness-проба не прошла | `kubectl logs <под>` |
| `CrashLoopBackOff` | контейнер падает, пауза между перезапусками растёт | `kubectl logs <под> --previous` |

| Docker | Kubernetes |
|---|---|
| `docker ps` | `kubectl get pods` |
| `docker logs -f api` | `kubectl logs -f deploy/api` |
| `docker exec -it api sh` | `kubectl exec -it deploy/api -- sh` |
| `docker inspect api` | `kubectl describe pod <под>` |
| `docker restart api` | `kubectl rollout restart deploy/api` |

### Остановка

| Команда | Что удаляет |
|---|---|
| `kubectl delete -f k8s/` | всё из манифестов вместе с PVC и данными монги, Secret остаётся |
| `minikube stop` | ничего, нода останавливается до `minikube start` |
| `minikube delete` | кластер целиком |

---

## 9. База в нескольких копиях

У api вторая копия получается сменой `replicas: 1` на `2`. С базой так не выйдет: обе монги взяли бы один и тот же диск, и на одном каталоге данных им не ужиться

База, которая переживает потерю одной копии или целой ноды, называется отказоустойчивой, HA (high availability). Для неё нужны другие объекты:

| Что нужно | Чем решается |
|---|---|
| свой диск у каждой копии | StatefulSet: поды с постоянными именами `db-0`, `db-1`, у каждого свой PVC |
| одинаковые данные на всех копиях | репликация: пишет одна копия, главная (primary), остальные повторяют за ней |
| замена упавшей главной | failover: одна из живых копий становится главной |
| запись всегда в главную | отдельный Service, который следует за главной |
| потеря ноды | копии разложены по разным нодам |

Обычно это берут готовым из HA-чарта, набора манифестов для Helm, где всё уже собрано. Бэкап при этом остаётся нужен, потому что удалённая по ошибке таблица исчезает сразу на всех копиях

---

## 10. Практика: проект в кластере

**Легенда.** Проект работает в compose на одной виртуалке. Команда переходит на Kubernetes, и проект нужно показать в кластере: с базой, с входом снаружи и без Helm

Готовая работа выглядит так:

| № | Что есть в итоге |
|---|---|
| 1 | Кластер minikube, поды проекта видны в Freelens |
| 2 | Образы проекта приходят из Docker Hub с тегом версии |
| 3 | Приложение и Postgres описаны манифестами, данные базы на PVC, приложение находит базу по имени Service |
| 4 | Настройки в ConfigMap, пароли и токены в Secret |
| 5 | Пробы, requests и limits у приложения и базы |
| 6 | Приложение открывается через Ingress на `localhost:8080` |

Результат: папка с манифестами в репозитории проекта, вывод `kubectl get pods,svc,ingress,pvc`, приложение, открытое через Ingress, скриншот подов из Freelens, ответы на два вопроса:

1. За что отвечает каждый объект в твоих манифестах
2. Что из твоего compose не перенеслось один в один и чем это заменено

---

## Что дальше

Урок 13: Helm. Манифесты станут шаблонами, и один набор файлов будет разворачиваться в разные окружения
