# 2. Несколько подов: манифесты и Helm-чарт

Поднимаем три приложения тремя способами:

| Приложение | Способ | Зачем так |
|---|---|---|
| mysql | чистые манифесты | видно все объекты, из которых собирается приложение |
| nginx | Helm-чарт | то же самое, только манифесты генерируются из шаблона |
| wildfly | одна команда `kubectl create` | быстрый способ, когда манифест не нужен |

| Объект | Что это |
|---|---|
| Pod | один или несколько контейнеров с общим IP и томами |
| Deployment | следит, чтобы было запущено нужное число подов, пересоздаёт упавшие |
| Service | постоянное имя и IP для группы подов, у самих подов IP меняется |
| Secret | пароли и токены, которые передаются в под |
| PersistentVolumeClaim (PVC) | запрос на диск, который переживёт пересоздание пода |

---

## mysql: чистые манифесты

Сохрани в файл `mysql.yaml`. Четыре объекта в одном файле, разделитель `---`:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mysql
type: Opaque
stringData:
  MYSQL_ROOT_PASSWORD: secret
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: mysql-data
spec:
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 1Gi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mysql
spec:
  replicas: 1
  # старый под отпускает диск до старта нового, два mysql на одном datadir не уживутся
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app: mysql
  template:
    metadata:
      labels:
        app: mysql
    spec:
      containers:
        - name: mysql
          image: mysql:8.4
          ports:
            - containerPort: 3306
          envFrom:
            - secretRef:
                name: mysql
          volumeMounts:
            - name: data
              mountPath: /var/lib/mysql
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: mysql-data
---
apiVersion: v1
kind: Service
metadata:
  name: mysql
spec:
  selector:
    app: mysql
  ports:
    - port: 3306
```

| Где | Что связывает |
|---|---|
| `selector.matchLabels` и `template.metadata.labels` | Deployment находит свои поды по метке `app: mysql` |
| `Service.spec.selector` | Service шлёт трафик в поды с той же меткой |
| `envFrom.secretRef` | ключи из Secret становятся переменными окружения контейнера |
| `claimName` | под монтирует диск из PVC |

```bash
kubectl apply -f mysql.yaml
```

Создаёт или обновляет все объекты из файла. Повторный запуск безопасен: применяются только изменения

```bash
kubectl get pods -w
```

Следит за подами в реальном времени. Ждём `Running`, выход по `ctrl+c`

```bash
kubectl exec -it deploy/mysql -- mysql -uroot -psecret -e "select version();"
```

Запускает клиент mysql внутри пода. Если ответ `Can't connect`, база ещё инициализируется, подожди полминуты

---

## nginx: Helm-чарт

Helm-чарт это папка с шаблонами манифестов и файлом `values.yaml`, из которого подставляются значения. Установленный чарт называется релизом

```bash
helm create web
```

Генерирует готовый чарт, который по умолчанию разворачивает nginx

| Файл | Что внутри |
|---|---|
| `web/Chart.yaml` | имя и версия чарта |
| `web/values.yaml` | настройки: образ, число реплик, тип сервиса |
| `web/templates/` | шаблоны Deployment, Service и прочего |

```bash
helm template web ./web
```

Печатает манифесты, которые получатся из шаблонов. Видно, что внутри те же Deployment и Service, что у mysql

```bash
helm install web ./web --set replicaCount=2
```

Устанавливает релиз `web`. `--set` переопределяет значение из `values.yaml`, получаем два пода nginx

```bash
kubectl port-forward svc/web 8080:80
```

Пробрасывает порт 8080 с твоей машины на сервис в кластере. Команда держит терминал, `curl` делаем во втором:

```bash
curl -I http://localhost:8080
```

| Команда | Что делает |
|---|---|
| `helm list` | установленные релизы |
| `helm upgrade web ./web --set replicaCount=3` | обновить релиз с новыми значениями |
| `helm history web` | история версий релиза |
| `helm rollback web 1` | откатиться на версию 1 |
| `helm uninstall web` | удалить релиз и все его объекты |

Чарт из публичного репозитория ставится так же, только сначала репозиторий подключается через `helm repo add <имя> <url>`, а настройки смотрятся через `helm show values <чарт>`. С чартами Bitnami осторожно: с осени 2025 их бесплатные образы переехали, и под может застрять в `ImagePullBackOff`. Причину покажет `kubectl describe pod`

---

## wildfly: одной командой

```bash
kubectl create deployment wildfly --image=quay.io/wildfly/wildfly
```

Создаёт Deployment без файла манифеста. Образ весит ~400 МБ, первый старт пару минут

```bash
kubectl port-forward deploy/wildfly 8081:8080
curl -I http://localhost:8081
```

Проброс прямо на Deployment, без Service

---

## Итог

```bash
kubectl get pods
```

Должно быть четыре пода в `Running`: mysql, два nginx (`web-...`), wildfly. Если какой-то в `Pending`, `ContainerCreating` или `CrashLoopBackOff`, разбираемся командами из пункта 3
