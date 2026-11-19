# 1. Minikube и визуализатор

Minikube поднимает Kubernetes из одной ноды. С драйвером `docker` вся нода живёт внутри одного Docker-контейнера, поэтому кроме Docker ничего не нужно. Все команды ниже набираются в терминале WSL

---

## Ресурсы для Docker

| Что | Сколько | Зачем |
|---|---|---|
| CPU | 4 | minikube, mysql и wildfly одновременно |
| Память | 6–8 ГБ | mysql и wildfly вместе едят около 1.5 ГБ, плюс сам Kubernetes |
| Диск | 20 ГБ свободно | образы и диск кластера |

Если Docker Desktop: `Settings → Resources`. Если Docker стоит прямо в WSL, память ограничивает файл `C:\Users\<имя>\.wslconfig`:

```ini
[wsl2]
memory=8GB
processors=4
```

После правки `.wslconfig` перезапусти WSL из PowerShell: `wsl --shutdown`

```bash
docker run --rm hello-world
```

Проверка, что Docker отвечает из WSL. Если `permission denied ... docker.sock`, добавь себя в группу docker и перезайди в терминал:

```bash
sudo usermod -aG docker $USER
```

---

## Установка kubectl, minikube, helm

```bash
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube
```

`minikube` создаёт и запускает кластер

```bash
curl -LO "https://dl.k8s.io/release/$(curl -Ls https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install kubectl /usr/local/bin/kubectl
```

`kubectl` основной клиент Kubernetes: всё, что делается с кластером, делается через него

```bash
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

`helm` пакетный менеджер для Kubernetes, ставит приложения готовыми чартами

```bash
minikube version
kubectl version --client
helm version
```

Проверка, что все три бинаря на месте

---

## Запуск кластера

```bash
minikube start --driver=docker --cpus=4 --memory=6g
```

| Флаг | Что делает |
|---|---|
| `--driver=docker` | нода кластера будет Docker-контейнером |
| `--cpus`, `--memory` | сколько ресурсов отдать ноде; должно влезать в лимиты Docker |

Первый запуск качает образ ноды на ~1 ГБ, это несколько минут. В конце minikube сам прописывает доступ к кластеру в `~/.kube/config`

```bash
kubectl get nodes
```

Нода `minikube` в статусе `Ready` значит, что кластер живой

```bash
docker ps
```

Видно контейнер `minikube`: это и есть весь кластер

```bash
minikube addons enable metrics-server
```

Включает сбор метрик CPU и памяти. Без него `kubectl top` из пункта 3 падает с `Metrics API not available`. Первые метрики появляются примерно через минуту

| Команда | Что делает |
|---|---|
| `minikube status` | состояние кластера |
| `minikube stop` | остановить кластер, всё сохранится |
| `minikube start` | запустить снова с теми же настройками |
| `minikube delete` | удалить кластер целиком |

---

## Визуализатор

### Что такое Lens

Lens это десктопное приложение для работы с Kubernetes, его называют «IDE для Kubernetes». Оно подключается к кластеру по тому же kubeconfig, что и kubectl, и показывает всё мышкой: ноды, поды, деплойменты, сервисы, логи, графики CPU и памяти, кнопку терминала внутрь пода. Внутри Lens делает те же запросы к API Kubernetes, что и kubectl, поэтому всё, что видно в Lens, можно получить командой и наоборот

Lens требует бесплатный аккаунт Lens ID. Freelens это открытый форк того же интерфейса без аккаунта, ставится с GitHub (freelensapp/freelens). Для тестового подойдёт любой

| Инструмент | Где работает | Когда брать |
|---|---|---|
| Lens / Freelens | Windows | хочется полноценный GUI |
| k9s | терминал WSL | быстро и без возни с kubeconfig для Windows |
| `minikube dashboard` | браузер | ничего не ставить |

### Lens на Windows + minikube в WSL

```bash
mkdir -p /mnt/c/Users/<windows-имя>/.kube
kubectl config view --minify --flatten > /mnt/c/Users/<windows-имя>/.kube/minikube.yaml
```

Выгружает kubeconfig в папку Windows. `--flatten` встраивает сертификаты прямо в файл: в обычном конфиге minikube лежат пути вида `/home/user/.minikube/ca.crt`, которые Windows-приложение прочитать не может

Дальше в Lens: настройки → Kubeconfigs → добавить файл `minikube.yaml`. Кластер появится в каталоге, по клику открываются ноды и поды

После каждого `minikube start` порт API может смениться, и Lens перестанет подключаться. Лечится повторной выгрузкой той же командой

### k9s в WSL

```bash
curl -LO https://github.com/derailed/k9s/releases/latest/download/k9s_Linux_amd64.tar.gz
tar xf k9s_Linux_amd64.tar.gz k9s
sudo install k9s /usr/local/bin/k9s
k9s
```

| Клавиша | Что делает |
|---|---|
| `:pods` | список подов |
| `l` | логи выбранного пода |
| `s` | shell внутрь пода |
| `d` | describe |
| `ctrl+d` | удалить |

### minikube dashboard

```bash
minikube dashboard --url
```

Печатает ссылку на веб-интерфейс Kubernetes Dashboard, открывается в браузере Windows. Команда должна оставаться запущенной, пока пользуешься дашбордом
