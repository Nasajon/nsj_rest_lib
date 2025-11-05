import datetime
import decimal
import re
import uuid

import unidecode

from typing import Any, Dict, List, Tuple

from nsj_rest_lib.entity.entity_base import EntityBase

from .dao_base_conjuntos import DAOBaseConjuntos

class DAOBaseSearch(DAOBaseConjuntos):

    def _make_search_sql(
        self,
        search_query: str,
        search_fields: List[str],
        entity: EntityBase,
    ) -> Tuple[Dict[str, Any], str]:
        """
        Monta a parte da cláusula where referente ao parâmetro search, bem como o mapa de
        valores para realizar a pesquisa (passando para a execução da query).

        Retorna uma tupla, onde a primeira posição é o mapa de valores, e a segunda a cláusula sql.
        """

        search_map = {}
        search_where = ""

        date_pattern = "(\d\d)/(\d\d)/((\d\d\d\d)|(\d\d))"
        int_pattern = "(\d+)"
        float_pattern = "(\d+((,|\.)\d+)?)"

        if search_fields is not None and search_query is not None:
            search_buffer = "false \n"
            for search_field in search_fields:
                search_str = search_query

                entity_field = entity.fields_map.get(search_field)
                if entity_field is None:
                    continue

                if (
                    entity_field.expected_type is datetime.datetime
                    or entity_field.expected_type is datetime.date
                ):
                    # Tratando da busca de datas
                    received_floats = re.findall(date_pattern, search_str)
                    cont = -1
                    for received_float in received_floats:
                        cont += 1

                        dia = int(received_float[0])
                        mes = int(received_float[0])
                        ano = received_float[0]
                        if len(ano) < 4:
                            ano = f"20{ano}"
                        ano = int(ano)

                        data_obj = None
                        try:
                            data_obj = datetime.date(ano, mes, dia)
                        except Exception:
                            continue

                        search_buffer += (
                            f" or t0.{search_field} = :shf_{search_field}_{cont} \n"
                        )
                        search_map[f"shf_{search_field}_{cont}"] = data_obj

                elif entity_field.expected_type is int:
                    # Tratando da busca de inteiros
                    search_str = re.sub(date_pattern, "", search_str)

                    received_floats = re.findall(int_pattern, search_str)
                    cont = -1
                    for received_float in received_floats:
                        cont += 1
                        valor = int(received_float[0])
                        valor_min = int(valor * 0.9)
                        valor_max = int(valor * 1.1)

                        search_buffer += f" or (t0.{search_field} >= :shf_{search_field}_{cont}_min and t0.{search_field} <= :shf_{search_field}_{cont}_max) \n"
                        search_map[f"shf_{search_field}_{cont}_min"] = valor_min
                        search_map[f"shf_{search_field}_{cont}_max"] = valor_max

                elif (
                    entity_field.expected_type is int
                    or entity_field.expected_type is decimal.Decimal
                ):
                    # Tratando da busca de floats e decimais
                    search_str = re.sub(date_pattern, "", search_str)

                    received_floats = re.findall(float_pattern, search_str)
                    cont = -1
                    for received_float in received_floats:
                        cont += 1
                        valor = float(received_float[0])
                        valor_min = valor * 0.9
                        valor_max = valor * 1.1

                        search_buffer += f" or (t0.{search_field} >= :shf_{search_field}_{cont}_min and t0.{search_field} <= :shf_{search_field}_{cont}_max) \n"
                        search_map[f"shf_{search_field}_{cont}_min"] = valor_min
                        search_map[f"shf_{search_field}_{cont}_max"] = valor_max

                elif (
                    entity_field.expected_type is str
                    or entity_field.expected_type is uuid
                ):
                    # Tratando da busca de strings e UUIDs
                    cont = -1
                    for palavra in search_str.split(" "):
                        if palavra == "":
                            continue

                        cont += 1
                        search_buffer += f" or upper(CAST(t0.{search_field} AS varchar)) like upper(unaccent(:shf_{search_field}_{cont})) \n"
                        search_map[f"shf_{search_field}_{cont}"] = (
                            f"%{unidecode.unidecode(palavra)}%"
                        )

            search_where = f"""
            and (
                {search_buffer}
            )
            """

        return search_map, search_where
