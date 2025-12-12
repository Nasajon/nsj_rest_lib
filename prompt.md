Gostaria de estender a funcionalidade suporte a funções de banco, hoje implementadas para as rotas de POST e PUT, para que também funcionem nas rotas de GET e DELETE.

Em resumo, para as rotas de GET:

- Preciso declarar a função a ser usada no GET.
- Preciso declarar o tipo de Objeto usado para mapear o retorno da função.
- Talvez não precise de um tipo novo de objeto... Talvez apenas o DTO (já suportar no GetRoute) seja suficiente.
- A ideia básica é que o objeto retornado pela função, que deve ser um type do postgres (um um array desse tyoe), seja mapeado para o DTO.
- Como entrada da função, preciso declarar um objeto, subcalsse de FunctionType, chamado: GetFunctionType, ou ListFunctionType. A ideia é que esse objeto, além de definir a função chamada, permita mapear os dados de entrada da função.
    - Se for uma função de Get by ID (e não List), e o tipo GetFunctionType for declarado, então o ID da entidade deve ser colocado na propriedade que for a PK do GetFunctionType. Se não tiver um GetFunctionType declarado, então o ID recebido na rota vira o primeiro parâmetro de entrada da função. Além disso, os query args são todos mapeados para o GetFunctionType.
    - Se for uma rota de List, todos os query args serão mapeados para o ListFunctionType.
- Creio que será preciso adicionar uma flag no FunctionField. para indicar qual campo seria a PK (pk=True).

Para as rotas de DELETE:

- Preciso declarar a função a ser usada no DELETE.
- Preciso declarar um tipo de objeto a ser usado, como um tipo de DTO, porém destinado a mapear o que for recebido como query args na chamada. A ideia é que, caso declarado, os query args viram uma instância desse ojeto, a ser passado como entrada na função de delete.
- Se houver um objeto, e ele tiver um campo de pk, esse campo receberá o ID contido na rota. Se não houver, o ID é passado como parâmetro de entrada da função a ser chamada.
    - Esse novo objeto seria de uma subclasse de FunctionType, chamada: DeleteFunctionType.



Por fim, quero criar um novo tipo de decorator para declarar rotas direto para funções (de modo bem livre)... Características:

- O nome do decorator será DBFunctionRoute.
- Deve receber os métodos HTTP suportados: GET, POST, PUT e/ou DELETE.
- 