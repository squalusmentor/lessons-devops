# Роадмап

Курс DevOps. Каждый урок опирается на предыдущие: то, что поднято руками в начале, дальше автоматизируется, потом уезжает в кластер

Linux, Bash и Git идут фоном самостоятельно, отдельными уроками они не разбираются

Параллельно идёт [курс по Python](https://github.com/squalusmentor/lessons-python). Он нужен, чтобы понимать изнутри приложения, которые разворачиваешь, и писать собственные инструменты автоматизации. Метки `L#` это основной курс, `B#` это модули из `advanced/`

---

## Уроки

1. [Статика и веб](lesson-1-base-web/): HTML/CSS/JS, запуск сервера, порты, HTTP, curl, кэш браузера

2. [nginx и Docker](lesson-2-nginx-docker/): конфиг веб-сервера, Dockerfile, сборка и запуск контейнера

3. [Деплой на сервер](lesson-3-server-deploy/): docker-compose, токен для приватного репозитория, Docker и порты на виртуалке, HTTPS с самоподписанным сертификатом

4. [Базовая отладка](lesson-4-debugging/): память, CPU и диск, чистка Docker-образов, load average, OOM и троттлинг, ping/traceroute, логи в Linux

   Python: [L1](https://github.com/squalusmentor/lessons-python/tree/main/l1), [L2](https://github.com/squalusmentor/lessons-python/tree/main/l2)

5. Приложение за прокси: reverse proxy, proxy_pass, заголовки X-Forwarded, переменные окружения, взаимодействие двух контейнеров, логи приложения в stdout

   Python: [L3](https://github.com/squalusmentor/lessons-python/tree/main/l3), [L4](https://github.com/squalusmentor/lessons-python/tree/main/l4)

6. Postgres и деплой: docker-сеть, healthcheck и готовность базы, volume и сохранность данных, .env и секреты, дамп базы, systemd unit и автозапуск после ребута

> **Здесь начинается собственный проект.** Темы на выбор: [project-list.md](project-list.md)
>
> Дальше проект едет через все оставшиеся уроки: попадает в пайплайн, разворачивается плейбуком, обрастает бэкапами и метриками, переезжает в кластер. К концу курса это работающий сервис в портфолио, а не набор учебных заготовок

7. CI/CD на GitHub Actions: ветки и теги, сборка образа, пуш в registry, секреты, триггеры, деплой, откат на предыдущую версию

   Python: [L5](https://github.com/squalusmentor/lessons-python/tree/main/l5)

8. Ansible: SSH, inventory, playbook, задачи, роли, идемпотентность, перенос ручного деплоя из уроков 3, 5 и 6 в плейбук

   Python: [L6](https://github.com/squalusmentor/lessons-python/tree/main/l6)

9. Ansible в пайплайне: отдельная джоба вызывает плейбук, весь деплой проекта собирается в одну кнопку

   Python: [L7](https://github.com/squalusmentor/lessons-python/tree/main/l7), основной курс закрыт

10. Бэкап на S3: работа с файлами и путями, subprocess, argparse, logging, boto3, дамп базы проекта, ротация копий, запуск по крону, уведомление об ошибке

11. Метрики: Prometheus, экспортеры, Netdata в контейнере, эндпоинт /metrics в проекте, что вообще имеет смысл считать

    Python: [B1](https://github.com/squalusmentor/lessons-python/tree/main/advanced/b1), [B2](https://github.com/squalusmentor/lessons-python/tree/main/advanced/b2)

12. Kubernetes: minikube, Pod, Deployment, Service, Ingress, ConfigMap, Secret, PVC, пробы, Lens, перенос приложения с базой в кластер, бэкап как CronJob

    Python: [B3](https://github.com/squalusmentor/lessons-python/tree/main/advanced/b3), [B4](https://github.com/squalusmentor/lessons-python/tree/main/advanced/b4)

13. Helm: шаблоны, values, разные окружения, установка и откат релиза, чарт под собственный проект

---

## Как читать связку с Python

Python идёт ровным ритмом и без длинных пауз, иначе первая половина курса забывается к моменту, когда она понадобится

До пятого урока хватает `L1` и `L2`: этого достаточно, чтобы читать код приложения и понимать, где роут, где конфиг, где обращение к базе

`L3` и `L4` идут плотно, двумя занятиями подряд. После `L4` появляется возможность написать собственное небольшое приложение и дальше его вести, поэтому проект стартует сразу за шестым уроком

Модули `B#` разбираются как чужой код. Задача этих модулей в том, чтобы устройство бэкенда перестало быть чёрным ящиком, а не в том, чтобы писать боевые приложения с нуля
