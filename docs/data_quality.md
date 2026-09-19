# Qualité des données

## Mes constats

| Constat                              | Règle                                   | Action                                        |
| ------------------------------------ | --------------------------------------- | --------------------------------------------- |
| Identifiant vide                     | `transaction_id` obligatoire            | Quarantaine                                   |
| Doublons exacts                      | Unicité de la ligne                     | Dédoublonner (conserver une seule occurrence) |
| Montant ≤ 0                          | Montant strictement positif             | Quarantaine                                   |
| Date hors format                     | Format `AAAA-MM-JJ HH:MM:SS` valide     | Quarantaine                                   |
| Devise `ZZZ`                         | Devise appartenant à la liste autorisée | Quarantaine                                   |
| Compte inconnu                       | Compte présent dans le référentiel      | Quarantaine                                   |
| Montants extrêmes, activité nocturne | Aucune règle appliquée                  | Conserver (relève du Projet 2)                |
