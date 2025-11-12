Agora que o insert by function está implementado, contando com ServiceBase e DAOBase próprios, contando com propretiy descriptor específico, contando com superclasse, decorator e até testes específicos (além de alterações nos decorator PostRoute, DTOField, DTOObjectField, DTOOneToOneField, DTOListField, etc). Então, gostaria que implementasse uma solução para Update By Function, o que será, em essência, uma quase duplicação da solução Insert By Function.

Minha ideia é criar nova classe base, novos properties descriptor, novo decorator, e, é claro, aterar também as propriedades dos decorators que vão utilizar o recurso (PostRoute, DTOField, DTOObjectField, DTOOneToOneField, DTOListField, etc), para suportar também o update.

Nessa replicação, só precisa adaptar os nomes. Por exemplo, a cópia do "InsertFunctionType" será chamada "UpdateFunctionType", a cópia do "insert_function_field" vira "update_function_field", e a cópia do "insert_function_type_class", usado no "PostRoute", deve se chamar, "update_function_type_class", mas, só deve estar disponível no "PutRoute" (não no "PostRoute").

No entanto, há também algumas refatorações no processo:

- Renomear o property descriptor "InsertFunctionField" para "FunctionField", porque, não faz sentido replicar e fazer diferença entre insert e update.
- Renomear as classes ServiceBaseInsertByFunction e DAOBaseInsertByFunction, para ServiceBaseSaveByFunction e DAOBaseSaveByFunction, respectivamente, porque me parece que os códigos de update e insert serão identicos (só mudando os nomes dos tipos e das funções).
- Nas classes que devem ser distintas, como "InsertFunctionType", creio que faz sentido criar superclasses| para conter o comportamento comum, e então estender adicionando o que for específico para Insert e Update (talvez a superclasse de InsertFunctionType seria FunctionType).

Ao final de tudo, não deixe de implementar os testes automáticos unitários (para os testes por APIs, depois te passo as estruturas de funções e tipos a usar, então podemos adiar um pouco).