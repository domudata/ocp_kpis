# -*- coding: utf-8 -*-
"""
PATCH — affichage des scores de cartes SANS décimale.

Seule la fonction render_cards() change : le format `%.1f%%` (qui
imposait toujours une décimale, ex. « 84.0% ») devient `%.0f%%`, pour
n'afficher que la partie entière du score, ex. « 84% ».

Remplace la fonction render_cards() existante dans components/cards.py.
Le reste du fichier (get_previous_card_values, format_card_variation)
est inchangé — format_card_variation garde sa décimale, car une
variation de « +0.4 % » entre deux périodes reste une information utile.
"""


def render_cards(total_ot, avg_p_score, avg_q_score,
                 total_ano, sf1_p, sf1_q, sf2_p, sf2_q,
                 prev_values: dict) -> None:

    var_p1 = format_card_variation(sf1_p, prev_values.get("Performance SF1"))
    var_q1 = format_card_variation(sf1_q, prev_values.get("Qualité SF1"))
    var_p2 = format_card_variation(sf2_p, prev_values.get("Performance SF2"))
    var_q2 = format_card_variation(sf2_q, prev_values.get("Qualité SF2"))

    # 4 cartes sur une seule ligne — scores affichés SANS décimale (%.0f)
    st.markdown(
        '<div class="cards">'
        '<div class="card c1"><div class="cv">%.0f%%</div>%s<div class="cl">Performance SF1</div></div>'
        '<div class="card c2"><div class="cv">%.0f%%</div>%s<div class="cl">Qualite SF1</div></div>'
        '<div class="card c3"><div class="cv">%.0f%%</div>%s<div class="cl">Performance SF2</div></div>'
        '<div class="card c4"><div class="cv">%.0f%%</div>%s<div class="cl">Qualite SF2</div></div>'
        '</div>' % (
            sf1_p, var_p1, sf1_q, var_q1,
            sf2_p, var_p2, sf2_q, var_q2
        ),
        unsafe_allow_html=True,
    )
