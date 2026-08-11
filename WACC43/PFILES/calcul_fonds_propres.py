def calcul_cout_fonds_propres(
    taux_sans_risque_local: float,
    beta_reendeté: float,
    prime_risque_marche: float,
    prime_taille: float,
    prime_specifique: float
) -> float:
    """
    Calcule le coût des fonds propres selon la formule :
    coût des fonds propres = a + b * c + d + e

    a : taux sans risque local
    b : beta réendetté
    c : prime de risque marché actions
    d : prime de taille
    e : prime spécifique
    """
    return taux_sans_risque_local + beta_reendeté * prime_risque_marche + prime_taille + prime_specifique


def parse_value(input_str: str) -> float:
    """
    Parse une valeur numérique avec support pour :
    - Virgules françaises (0,2)
    - Pourcentages (3% ou 3,5%)
    - Format classique (0.2)
    """
    value = input_str.strip()
    
    # Vérifier si c'est un pourcentage
    is_percentage = "%" in value
    
    # Nettoyer la valeur
    value = value.replace("%", "").replace(",", ".").strip()
    
    # Convertir en float
    result = float(value)
    
    # Diviser par 100 si c'était un pourcentage
    if is_percentage:
        result /= 100
    
    return result


if __name__ == "__main__":
    print("Calcul du coût des fonds propres")
 
    
    a = parse_value(input("Taux sans risque local : "))
    b = parse_value(input("Beta réendetté : "))
    c = parse_value(input("Prime de risque marché actions : "))
    d = parse_value(input("Prime de taille : "))
    e = parse_value(input("Prime spécifique : "))

    cout_fonds_propres = calcul_cout_fonds_propres(a, b, c, d, e)
    print(f"\nCoût des fonds propres : {cout_fonds_propres:.3%}")
