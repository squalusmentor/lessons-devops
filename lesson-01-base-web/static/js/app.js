/* ===========================================================================
   app.js — наш JavaScript.

   Файл лежит:         static/js/app.js
   По HTTP отдаётся:   /js/app.js
   Подключён в head.html:  <script src="/js/app.js" defer></script>

   ГЛАВНОЕ, ЧТО НУЖНО ПОНЯТЬ ПРО JS В ЭТОМ УРОКЕ:
   он выполняется НЕ на сервере, а в БРАУЗЕРЕ пользователя.
   Сервер просто отдал текстовый файл, как отдал бы картинку.

   Отсюда следуют два практических вывода:
     1. В JS фронтенда нельзя класть пароли и токены — любой откроет
        http://localhost:1313/js/app.js и прочитает их.
     2. Ошибка в JS не роняет сервер: страница отдастся, но что-то
        на ней не заработает. Смотреть такие ошибки — DevTools -> Console.

   Комментарии в JS: // до конца строки или /* ... *\/ блоком.
   =========================================================================== */

/* IIFE — функция, которая объявляется и тут же вызывается.
   Зачем: всё, что внутри, не вылезает в глобальную область видимости
   и не столкнётся с переменными Bootstrap или другой библиотеки. */
(function () {
  'use strict';   // строгий режим: JS ругается на подозрительный код вместо того, чтобы молча его глотать

  // -------------------------------------------------------------------------
  // 1. КАК JS НАХОДИТ ЭЛЕМЕНТЫ НА СТРАНИЦЕ
  //
  //    document                       — вся страница целиком
  //    document.getElementById('x')   — элемент с id="x" (или null)
  //    document.querySelector('.c')    — ПЕРВЫЙ подходящий по CSS-селектору
  //    document.querySelectorAll('.c') — ВСЕ подходящие, списком
  //
  //    Селекторы — те же самые, что в CSS. Одна система на весь фронтенд.
  // -------------------------------------------------------------------------

  var info = document.getElementById('js-info');
  if (info) {
    // textContent — заменить текст внутри элемента.
    // Если этот текст появился на странице — значит, файл доехал и выполнился.
    info.textContent =
      'JavaScript отработал. Этого текста нет в исходнике страницы (Ctrl+U) — ' +
      'он появился уже в браузере. Адрес: ' + window.location.href;
  }

  var openedAt = document.getElementById('opened-at');
  if (openedAt) {
    // Время берётся с ТВОЕГО компьютера, а не с сервера
    openedAt.textContent = new Date().toLocaleTimeString('ru-RU');
  }


  // -------------------------------------------------------------------------
  // 2. РЕАКЦИЯ НА СОБЫТИЯ: переключатель темы
  //
  //    addEventListener('click', функция) = "когда кликнут, вызови эту функцию".
  //    Внутри мы просто добавляем/снимаем CSS-класс на <body>.
  //    Дальше всю работу делает CSS: правила body.theme-light из style.css
  //    подменяют значения переменных, и весь сайт перекрашивается.
  //
  //    Это типичное разделение труда: JS переключает классы, CSS рисует.
  // -------------------------------------------------------------------------

  var toggle = document.getElementById('theme-toggle');
  if (toggle) {
    toggle.addEventListener('click', function () {
      document.body.classList.toggle('theme-light');

      // localStorage — маленькое хранилище прямо в браузере.
      // Переживает перезагрузку страницы и закрытие вкладки.
      // Это НЕ кэш и НЕ куки: на сервер оно не отправляется никогда.
      var isLight = document.body.classList.contains('theme-light');
      localStorage.setItem('theme', isLight ? 'light' : 'dark');

      // console.log пишет в DevTools -> Console. Главный инструмент отладки.
      console.log('[lesson-1] тема переключена на:', isLight ? 'light' : 'dark');
    });
  }

  // Восстановить тему, выбранную в прошлый раз
  if (localStorage.getItem('theme') === 'light') {
    document.body.classList.add('theme-light');
  }


  // -------------------------------------------------------------------------
  // 3. КОПИРОВАНИЕ В БУФЕР — этот же приём работает на реальном сайте
  //
  //    Слушаем клик не на кнопке, а на всём документе, и уже потом проверяем,
  //    попали ли по нужному элементу (event.target.closest). Так один
  //    обработчик обслуживает сколько угодно кнопок, в том числе появившихся
  //    после загрузки страницы.
  // -------------------------------------------------------------------------

  document.addEventListener('click', function (event) {
    var button = event.target.closest('.copy-email');
    if (!button) return;   // кликнули мимо — выходим

    // Читаем СВОЙ атрибут data-email из HTML
    var email = button.getAttribute('data-email');
    if (!email) return;

    // navigator.clipboard работает только в "безопасном контексте":
    // https:// или localhost. По http на чужой IP — не сработает,
    // и это не баг, а требование безопасности браузера.
    navigator.clipboard.writeText(email).then(function () {
      var label = button.querySelector('.copy-email-text');
      var original = label.textContent;
      label.textContent = 'Скопировано!';
      label.classList.add('copied');

      // setTimeout — выполнить функцию через N миллисекунд
      setTimeout(function () {
        label.textContent = original;
        label.classList.remove('copied');
      }, 1500);
    }).catch(function () {
      // Не получилось — не молчим, а даём человеку скопировать руками
      window.prompt('Скопируй вручную:', email);
    });
  });


  // -------------------------------------------------------------------------
  // 4. СЛЕД В КОНСОЛИ
  //
  //    Открой DevTools (F12) -> Console и перезагрузи страницу.
  //    performance.timing показывает, сколько миллисекунд ушло на загрузку.
  //    Сравни первую загрузку и повторную: вторая будет заметно быстрее —
  //    часть файлов браузер возьмёт из кэша, не спрашивая сервер.
  // -------------------------------------------------------------------------

  window.addEventListener('load', function () {
    var nav = performance.getEntriesByType('navigation')[0];
    if (nav) {
      console.log('[lesson-1] страница загрузилась за', Math.round(nav.duration), 'мс');
      console.log('[lesson-1] тип навигации:', nav.type,
                  '(reload = перезагрузка, navigate = обычный переход)');
    }
    console.log('[lesson-1] всего загружено ресурсов:',
                performance.getEntriesByType('resource').length,
                '— это те самые запросы из вкладки Network');
  });

})();
