---
title: {{ group }}
---

# {{ group }}

<ul>
{% for link, title in algorithms %}
    <li>
        <a href="{{ link }}">{{ title }}</a>
    </li>
{% endfor %}
<ul>