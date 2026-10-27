# Tutorial TwinCAT 3

Fuente original: Tutorial TwinCAT 3.pdf
Fabricante: Beckhoff (material didáctico)


<!-- Página PDF 1 -->

TUTORIAL
TwinCAT 3

Teoría, programación en Structured Text y fundamentos de
automatización PC-Based Control

TwinCAT: The Windows Control and Automation Technology.

Guía didáctica basada en los videos procesados y documentación técnica Beckhoff incluida en el material de
estudio.

![Recurso gráfico de la página 1](assets_v2/imagen_b31fc7b8225e8731.jpeg)


<!-- Página PDF 2 -->

Cómo usar este tutorial

Este documento propone un recorrido progresivo por TwinCAT 3. Primero se prepara el entorno de
trabajo, luego se construye una imagen mental del sistema, se aprende a programar un PLC en Structured
Text y finalmente se conectan esos conocimientos con tiempo real, EtherCAT, ADS, librerías, diagnóstico y
prácticas de ingeniería de software.

  Lee los capítulos 1 a 6 en orden si estás comenzando desde cero.
   Escribe y prueba los ejemplos: no basta con leer Structured Text.
  En modo online observa cómo cambian las variables en cada ciclo.
  No fuerces salidas físicas reales durante una práctica sin conocer el estado seguro de la máquina.
   Los ejemplos son pequeños a propósito: cada uno introduce una sola idea.

Idea clave: TwinCAT se aprende mejor relacionando tres capas: el código PLC, la ejecución cíclica en tiempo real
y el hardware/proceso físico. Cada vez que aparezca un concepto nuevo, pregúntate en cuál de esas capas actúa.


<!-- Página PDF 3 -->

<!-- Página PDF 4 -->

## 1. Descarga, registro e instalación de TwinCAT 3

Antes de programar conviene dejar preparado el entorno. En las versiones actuales de TwinCAT
3.1 Build 4026 y posteriores para Windows, Beckhoff distribuye TwinCAT mediante TwinCAT
Package Manager. Para descargar y utilizar este mecanismo se necesita una cuenta myBeckhoff.

### 1.1 Dónde se descarga TwinCAT 3

La fuente recomendada es el sitio oficial de Beckhoff. Desde Support > Download finder puedes buscar
“TwinCAT 3”, “TwinCAT 3 XAE” o “TwinCAT Package Manager”. En la lista aparecen, entre otros,
TwinCAT 3 Engineering (XAE), TwinCAT Runtime (XAR), Remote Manager y el propio Package Manager.

Para un equipo de aprendizaje en el que programarás y también ejecutarás ejemplos localmente,
normalmente te interesa instalar TwinCAT Engineering (XAE) y disponer de un Runtime local. En Build
4026 esto se resuelve desde el workload TwinCAT Standard, seleccionando los componentes de
Engineering y Runtime que necesites.

Ruta de descarga e instalación recomendada para TwinCAT 3.1 Build 4026 y posteriores. Esquema didáctico basado en la
documentación oficial de Beckhoff.

### 1.2 Crear o usar una cuenta myBeckhoff

Beckhoff requiere iniciar sesión para descargar software. Si aún no tienes una cuenta, selecciona la
opción de crear una nueva cuenta myBeckhoff, completa los campos obligatorios y acepta las condiciones
indicadas por el portal.

Después del registro recibirás un correo de activación. La cuenta debe activarse antes de usarla para
descargar software. Una vez activada, vuelve al portal, inicia sesión con tu correo y contraseña y regresa
al Download finder o a la página del producto que estabas consultando.

![Recurso gráfico de la página 4](assets_v2/imagen_a9e87586cd8b3f9c.png)


<!-- Página PDF 5 -->

Idea clave: La cuenta myBeckhoff no es una licencia de ejecución. Sirve, entre otras funciones, para acceder a
descargas y al historial de software. Las licencias de TwinCAT y de sus Functions se gestionan por separado.

### 1.3 Descargar e instalar TwinCAT Package Manager

Para TwinCAT 3.1 Build 4026 y posteriores en Windows, descarga el instalador de TwinCAT Package
Manager desde el área de descargas de Beckhoff. Ejecuta el instalador, acepta el acuerdo de licencia y
completa la instalación.

Al abrir TwinCAT Package Manager por primera vez aparece un asistente de configuración. Allí se
definen los feeds desde los que se obtienen los paquetes y, si vas a instalar Engineering, la integración
con TwinCAT XAE Shell o con una versión compatible de Visual Studio. Si el equipo ya tenía Build 4024 o
una versión anterior, el asistente puede mostrar además opciones de migración.

### 1.4 Instalar TwinCAT Standard

Dentro de TwinCAT Package Manager, entra en la vista de software disponible y selecciona el workload
TwinCAT Standard. Un workload agrupa paquetes que juntos forman una funcionalidad completa; por
eso resulta preferible instalar el workload en lugar de elegir paquetes aislados sin conocer sus
dependencias.

Para estudiar en un solo PC, selecciona Engineering (XAE) y Runtime (XAR) cuando estén disponibles para
la versión elegida. Revisa la versión del workload y pulsa Install. El Package Manager resolverá las
dependencias y descargará los componentes necesarios.

Selección conceptual de TwinCAT Standard en TwinCAT Package Manager. La disposición exacta de controles puede variar
entre versiones.

### 1.5 Qué elegir: XAE, XAR y entorno de desarrollo

XAE contiene las herramientas de ingeniería: edición, configuración, compilación, conexión al target y
diagnóstico. XAR es el entorno de ejecución. En una estación de ingeniería puedes instalar sólo XAE si el

![Recurso gráfico de la página 5](assets_v2/imagen_bdca91ba2675495f.png)


<!-- Página PDF 6 -->

runtime estará en un IPC remoto; para practicar sin hardware adicional resulta cómodo disponer
también de un runtime local.

TwinCAT Engineering puede integrarse con un entorno Visual Studio compatible o utilizar TwinCAT XAE
Shell, según la configuración y los componentes instalados. No necesitas instalar Visual Studio por
separado para todas las prácticas PLC si utilizas XAE Shell; requisitos adicionales aparecen cuando
trabajas con funciones específicas, por ejemplo desarrollo C++.

Componente                             Cuándo lo necesitas

Para instalar, actualizar o quitar TwinCAT 3.1 TwinCAT Package Manager
Build 4026 y componentes relacionados.
Para crear proyectos, programar PLC, configurar XAE / Engineering
E/S y desplegar.
Para ejecutar la configuración TwinCAT en el XAR / Runtime
equipo target.
Entorno de ingeniería proporcionado por
TwinCAT XAE Shell                         TwinCAT cuando no se usa una instalación Visual
Studio compatible.
Para trabajar desde una instalación actual con
Remote Manager                                     toolsets de ingeniería de versiones anteriores
cuando corresponda.

### 1.6 Primer arranque y comprobaciones

Después de instalar, reinicia Windows si el instalador o Package Manager lo solicita. Abre TwinCAT XAE y
verifica que puedes crear una solución o proyecto TwinCAT. También comprueba el icono/estado de
TwinCAT en el área de notificación y que puedes cambiar entre los modos permitidos por tu instalación.

Si utilizarás un target remoto, la comunicación se configura más adelante mediante rutas ADS y selección
del target. Para las primeras prácticas puedes trabajar con variables internas y un runtime local,
evitando depender todavía de EtherCAT o hardware físico.

  Usa siempre el sitio oficial de Beckhoff para descargar el instalador y los paquetes.
  Mantén anotada la versión/build de TwinCAT instalada; será importante al abrir proyectos y
seleccionar librerías.
   Si ya existe TwinCAT 3.1 Build 4024 en el equipo, no trates Build 4026 como una actualización
convencional: la documentación actual de Beckhoff indica realizar la migración mediante TwinCAT
Package Manager.
   Antes de actualizar un equipo de producción, respalda el proyecto y revisa compatibilidad, licencias y
ventanas de parada.

Idea clave: En este tutorial los menús y capturas se describen de forma conceptual. Beckhoff actualiza TwinCAT
y el Package Manager, por lo que algunos nombres o posiciones pueden cambiar; el flujo general - cuenta,
descarga, Package Manager, workload y selección XAE/XAR - es el punto que debes reconocer.


<!-- Página PDF 7 -->

## 2. Qué es TwinCAT 3 y dónde encaja en la automatización

TwinCAT 3 convierte un PC compatible en una plataforma de automatización: combina
herramientas de ingeniería, ejecución determinista, comunicación industrial y programación
PLC bajo un mismo ecosistema.

### 2.1 Del PLC clásico al PC-Based Control

Un PLC ejecuta lógica de control de forma repetitiva y predecible. En lugar de cablear cada decisión con
relés, el comportamiento se expresa en software. Beckhoff lleva esta idea al PC-Based Control: un
computador industrial puede ejecutar control PLC, motion, comunicaciones y otras funciones de
automatización.

TwinCAT significa The Windows Control and Automation Technology. TwinCAT 3 integra la ingeniería en
un entorno basado en Visual Studio y separa conceptualmente el entorno de desarrollo del entorno que
ejecuta la aplicación de control.

Vista simplificada de la separación entre ingeniería y ejecución.

### 2.2 Conceptos que debes distinguir

XAE (eXtended Automation Engineering) es el entorno de ingeniería: allí se crea la solución, se configura
el sistema, se programa, compila y despliega. XAR (eXtended Automation Runtime) es el runtime que
ejecuta las tareas de automatización en el target.

El target puede ser el mismo equipo de desarrollo o un IPC/CX remoto. Esta separación es importante
porque permite desarrollar desde una estación y ejecutar en otro dispositivo industrial.

Término                                      Idea principal

![Recurso gráfico de la página 7](assets_v2/imagen_479be0b287948273.jpeg)


<!-- Página PDF 8 -->

Ingeniería, configuración, edición, compilación y XAE
despliegue.
Ejecución de tareas de automatización en el XAR
sistema destino.
Proyecto que contiene POUs, tipos, variables y PLC project
referencias.
Target                                       Equipo donde se activa y ejecuta la configuración.
Conjunto de servicios que ejecutan la aplicación Runtime
en tiempo real.

Idea clave: No confundas Visual Studio con el PLC. Visual Studio/XAE es la herramienta con la que preparas el
proyecto; el control real ocurre en el runtime TwinCAT del target.


<!-- Página PDF 9 -->

## 3. Arquitectura XAE, XAR y flujo de un proyecto

Antes de escribir código conviene entender qué sucede desde que editas una línea hasta que esa
lógica controla una entrada o una salida.

### 3.1 Flujo de ingeniería

Un proyecto típico sigue este recorrido: crear solución -> agregar proyecto TwinCAT/PLC -> configurar
target -> definir tareas y POUs -> compilar -> activar configuración -> iniciar runtime -> iniciar sesión en
el PLC -> observar/depurar.

La configuración del sistema y el programa PLC están relacionados pero no son lo mismo. La
configuración define, entre otras cosas, tareas, dispositivos y enlaces de E/S; el PLC project define el
software IEC 61131-3.

Integración de las herramientas de TwinCAT 3 en el entorno de ingeniería.

### 3.2 Estados y acciones frecuentes

Build comprueba y compila el proyecto. Activate Configuration transfiere/activa cambios del sistema.
Login conecta el entorno de ingeniería con la instancia PLC. Run inicia la ejecución de la lógica. Online
Change permite transferir determinados cambios de código conservando el estado, cuando la
modificación es compatible.

En un entorno industrial debes diferenciar claramente un cambio de código, una activación de
configuración y un reinicio del runtime: sus efectos sobre la máquina pueden ser distintos.

![Recurso gráfico de la página 9](assets_v2/imagen_7db2b3332fe245a9.jpeg)


<!-- Página PDF 10 -->

## 4. Tiempo real, tareas, ciclos y programas PLC

TwinCAT no ejecuta el programa como una aplicación de escritorio que “corre una vez”. Las
tareas de tiempo real llaman al código de forma cíclica según una planificación configurada.

### 4.1 Por qué importa el determinismo

Windows por sí solo no garantiza que una instrucción de usuario se ejecute exactamente cada cierto
intervalo. En control industrial, en cambio, el momento de leer sensores, calcular la lógica y actualizar
actuadores puede ser tan importante como el resultado lógico.

TwinCAT incorpora un entorno de tiempo real y tareas configurables. Una tarea dispone de parámetros
como tiempo de ciclo, prioridad y afinidad de CPU. El código PLC asignado a la tarea se ejecuta conforme
a ese ciclo.

El código creado en XAE se ejecuta en el runtime XAR bajo tareas de tiempo real.

### 4.2 Modelo mental de un ciclo

Una forma útil de pensar un ciclo PLC es: obtener entradas/proceso de imagen -> ejecutar lógica ->
producir valores de salida -> sincronizar comunicaciones/E/S según la configuración. Los detalles
dependen de la tarea y del bus, pero este modelo ayuda a razonar sobre el comportamiento.

Si una tarea tiene un ciclo de 10 ms, su lógica está prevista para ejecutarse aproximadamente 100 veces
por segundo. El tiempo de ejecución real debe permanecer suficientemente por debajo del tiempo de ciclo
para dejar margen al sistema.

PROGRAM MAIN
VAR
nCycles : UDINT;

![Recurso gráfico de la página 10](assets_v2/imagen_e0bd03965dc483d2.jpeg)


<!-- Página PDF 11 -->

END_VAR

nCycles := nCycles + 1;
Qué hace y cómo funciona. Cada vez que la tarea llama a MAIN, nCycles aumenta en uno. En modo
online verás que crece rápidamente. El ejemplo muestra que un programa PLC se evalúa de forma cíclica:
no termina después de la asignación.

### 4.3 Jitter, sobrecarga y prioridades

Jitter es la variación temporal respecto del instante ideal de ejecución. Una tarea que consume demasiado
tiempo, prioridades mal definidas o cargas adicionales pueden degradar el comportamiento temporal. La
puesta en marcha debe considerar tiempo de ejecución, carga de CPU y necesidades reales del proceso.

Una regla práctica para aprender es elegir ciclos moderados y sólo reducirlos cuando exista una razón de
proceso. Un ciclo más rápido no hace automáticamente mejor al sistema; aumenta la carga y puede
volver más exigente el diagnóstico.


<!-- Página PDF 12 -->

## 5. Primer proyecto: de la solución al “Hello World”

Este capítulo conecta la teoría con el flujo mínimo que un estudiante debe dominar para
comprobar que su entorno TwinCAT funciona.

### 5.1 Secuencia práctica

Crea un proyecto TwinCAT, selecciona o añade el target, agrega un PLC project estándar y localiza MAIN.
Compila antes de activar. Después activa la configuración, inicia sesión y ejecuta el PLC. Los nombres
exactos de menús pueden variar entre builds, pero el flujo conceptual se mantiene.

Para la primera práctica no necesitas hardware real: basta una variable interna observable. Cuando
domines login, run, stop, build y monitorización online, puedes añadir E/S.

PROGRAM MAIN
VAR
bHello : BOOL := TRUE;
nValue : INT := 10;
END_VAR

IF bHello THEN
nValue := nValue + 1;
END_IF;
Qué hace y cómo funciona. bHello habilita el incremento. Mientras sea TRUE, cada ciclo incrementará
nValue. En el editor online puedes observar nValue y cambiar bHello para comprobar cómo la lógica
responde en el siguiente ciclo.

Idea clave: Si nValue llega al máximo de INT, el comportamiento de overflow deja de ser didáctico. Para una
práctica prolongada utiliza DINT/UDINT o reinicia el contador deliberadamente.


<!-- Página PDF 13 -->

## 6. Structured Text: variables, tipos de datos y operadores

Structured Text (ST) es un lenguaje textual de IEC 61131-3 comparable en estilo a lenguajes de
alto nivel. En TwinCAT también existe ExST, una extensión específica del entorno.

### 6.1 Declarar antes de usar

En un proyecto PLC las variables pueden declararse en POUs, DUT y GVL, entre otros lugares. ST es
fuertemente tipado: cada variable tiene un tipo que define representación, rango y operaciones válidas.

Entre los tipos comunes están BOOL, SINT/INT/DINT/LINT y sus variantes sin signo, REAL/LREAL,
BYTE/WORD/DWORD/LWORD, STRING/WSTRING y tipos temporales como TIME, DATE y DT.

Ejemplo visual de tipos enteros IEC 61131 utilizados en TwinCAT.

VAR
bMotorEnable : BOOL := FALSE;
nPieces     : UDINT := 0;
rTemperature : REAL := 21.5;
sState      : STRING(30) := 'READY';
tDelay      : TIME := T#2S;
END_VAR
Qué hace y cómo funciona. Cada variable tiene un propósito distinto. BOOL representa una condición
lógica; UDINT un conteo no negativo; REAL una magnitud con decimales; STRING texto y TIME una
duración. Inicializar valores hace más predecible el arranque del ejemplo.

### 6.2 Operadores y conversiones

La asignación en ST utiliza :=. Las comparaciones típicas son =, <>, <, <=, > y >=. Para lógica booleana se
usan AND, OR, XOR y NOT. En expresiones numéricas son comunes +, -, *, / y MOD.

Evita depender de conversiones implícitas difíciles de leer. Cuando mezcles tipos o escales datos de
proceso, usa conversiones explícitas y comprueba el rango destino.

rPercent := UDINT_TO_REAL(nCount) / UDINT_TO_REAL(nTotal) * 100.0;

![Recurso gráfico de la página 13](assets_v2/imagen_55145f5bbe8e8c6b.jpeg)


<!-- Página PDF 14 -->

Qué hace y cómo funciona. Convierte ambos enteros a REAL antes de dividir. Esto expresa claramente
que se busca una división de punto flotante y produce un porcentaje decimal.


<!-- Página PDF 15 -->

## 7. Arrays, estructuras, referencias y organización de datos

Cuando el proyecto crece, la calidad del modelo de datos comienza a ser tan importante como la
lógica. TwinCAT permite agrupar y recorrer información de forma estructurada.

### 7.1 Arrays

Un ARRAY almacena elementos del mismo tipo indexados por un rango explícito. Es especialmente útil
para sensores repetitivos, historiales, buffers o tablas.

Representación de arrays en TwinCAT.

VAR
aTemp : ARRAY[1..4] OF REAL := [20.0, 20.5, 21.0, 21.5];
i     : INT;
rSum  : REAL;
END_VAR

rSum := 0.0;
FOR i := 1 TO 4 DO
rSum := rSum + aTemp[i];
END_FOR;
Qué hace y cómo funciona. El FOR recorre los cuatro elementos y acumula su valor. El rango del bucle
coincide con los límites declarados del array; esta relación debe mantenerse para evitar accesos
inválidos.

### 7.2 DUT y STRUCT

Una estructura agrupa campos de tipos distintos bajo un único tipo de datos definido por el usuario
(DUT). Esto mejora la legibilidad porque un objeto conceptual -por ejemplo, un evento- viaja como una
sola unidad.

![Recurso gráfico de la página 15](assets_v2/imagen_c5616d35ff584aa2.jpeg)


<!-- Página PDF 16 -->

Las estructuras permiten reunir datos relacionados bajo un mismo tipo.

TYPE ST_Event :
STRUCT
nId      : UDINT;
sMessage  : STRING(80);
nSeverity : USINT;
dtCreated : DT;
END_STRUCT
END_TYPE
Qué hace y cómo funciona. ST_Event define el formato de un evento. Luego puedes declarar variables,
arrays o entradas de función de tipo ST_Event. La estructura no ejecuta lógica: organiza datos.

### 7.3 Referencias y punteros

TwinCAT soporta referencias y punteros para escenarios donde copiar datos no es conveniente o se
necesita acceder a memoria de forma indirecta. Son herramientas poderosas, pero también elevan el
riesgo de errores si se usan sin una necesidad clara.

Para comenzar, prefiere parámetros por valor para datos pequeños y referencias/VAR_IN_OUT cuando
necesites operar sobre un objeto existente. Reserva punteros para APIs o patrones que realmente los
requieran.

![Recurso gráfico de la página 16](assets_v2/imagen_5c4d3008768d29df.jpeg)


<!-- Página PDF 17 -->

## 8. Funciones, bloques de función y orientación a objetos

Las POUs permiten separar responsabilidades. Una función calcula un resultado sin conservar
estado de instancia; un Function Block (FB) representa una unidad con estado propio y puede
exponer métodos.

### 8.1 FUNCTION

Una función es adecuada para transformaciones deterministas de datos, cálculos o validaciones. Puede
recibir entradas y devolver un valor de retorno.

FUNCTION CelsiusToFahrenheit : REAL
VAR_INPUT
rCelsius : REAL;
END_VAR

CelsiusToFahrenheit := rCelsius * 1.8 + 32.0;
Qué hace y cómo funciona. La función recibe grados Celsius y devuelve Fahrenheit. No necesita
conservar memoria entre llamadas; el mismo valor de entrada produce el mismo resultado.

### 8.2 FUNCTION_BLOCK e instancia

Un FB tiene memoria de instancia. Dos variables declaradas con el mismo tipo de FB son dos objetos
distintos: cada uno conserva sus propios datos. Esto lo hace natural para representar motores, válvulas,
estaciones o servicios de software.

Los Function Blocks combinan comportamiento y estado de instancia.

FUNCTION_BLOCK FB_Motor
VAR_INPUT
bEnable : BOOL;
END_VAR
VAR_OUTPUT
bRunning : BOOL;

![Recurso gráfico de la página 17](assets_v2/imagen_1a8caae97c7c076f.jpeg)


<!-- Página PDF 18 -->

END_VAR

bRunning := bEnable;
Qué hace y cómo funciona. FB_Motor encapsula una entrada y un estado de salida. Si declaras fbMotor1
y fbMotor2, cada instancia recibe su propio bEnable y conserva su propio espacio de memoria.

### 8.3 Métodos, encapsulación y herencia

Los métodos permiten colocar operaciones cerca de los datos que gestionan. Los modificadores de acceso
ayudan a ocultar detalles internos. TwinCAT también permite herencia mediante EXTENDS; úsala cuando
exista una relación conceptual clara, no sólo para reutilizar unas líneas.

Un diseño PLC mantenible suele limitar variables globales y ofrecer a otros módulos únicamente las
operaciones necesarias.


<!-- Página PDF 19 -->

## 9. Interfaces, abstracción e inyección de dependencias

Las interfaces describen comportamiento sin imponer una implementación concreta. Esta idea
reduce acoplamiento y facilita cambiar hardware, almacenamiento o servicios sin reescribir
toda la aplicación.

Una interfaz actúa como contrato entre quien usa un servicio y quien lo implementa.

### 9.1 Contratos

Una interfaz puede declarar métodos. Un FB que la implementa mediante IMPLEMENTS debe
proporcionar ese comportamiento. El consumidor trabaja contra la interfaz y no necesita conocer todos
los detalles de la clase concreta.

INTERFACE I_AlarmSink
METHOD Store : BOOL
VAR_INPUT
stEvent : ST_Event;
END_VAR
END_INTERFACE
Qué hace y cómo funciona. I_AlarmSink define que cualquier implementación capaz de almacenar
alarmas debe ofrecer Store. No dice si el destino será memoria, CSV, base de datos o un servicio externo.

### 9.2 Inyección de dependencias

En lugar de crear dependencias rígidas dentro del módulo, puedes entregar una implementación desde
fuera. Así un EventLogger puede recibir un almacenamiento real en producción y uno falso durante las
pruebas.

![Recurso gráfico de la página 19](assets_v2/imagen_460e00a07d0303b5.jpeg)


<!-- Página PDF 20 -->

La inyección de dependencias desacopla el consumidor de la implementación concreta.

Idea clave: El valor de una interfaz aparece cuando existen varias implementaciones, cuando quieres probar el
módulo aisladamente o cuando esperas sustituir un componente. No agregues interfaces por rutina si sólo
complican un caso trivial.

![Recurso gráfico de la página 20](assets_v2/imagen_e32e7ba3e2dab4ea.jpeg)


<!-- Página PDF 21 -->

## 10. Control de flujo y máquinas de estados

IF, CASE, FOR y WHILE controlan qué instrucciones se ejecutan. En automatización, CASE
también es una herramienta muy útil para expresar secuencias no bloqueantes.

### 10.1 Decisiones

IF es apropiado para condiciones simples o jerárquicas. CASE es especialmente legible cuando una
variable de estado selecciona entre modos discretos.

IF rTemp > 80.0 THEN
bAlarm := TRUE;
ELSIF rTemp < 75.0 THEN
bAlarm := FALSE;
END_IF;
Qué hace y cómo funciona. Se implementa una histéresis simple: la alarma se activa sobre 80 °C y no se
desactiva hasta bajar de 75 °C. La separación de umbrales evita conmutaciones rápidas alrededor de un
único límite.

### 10.2 Bucles

FOR es la opción natural cuando conoces el número de iteraciones. WHILE depende de una condición y
debe usarse con cuidado en tareas de tiempo real: una condición que nunca cambie puede consumir todo
el ciclo.

CASE facilita representar ramas de ejecución o estados de una secuencia.

### 10.3 Máquina de estados no bloqueante

Muchos bloques de comunicación y sistema trabajan de forma asíncrona: se inicia una operación, el FB
marca bBusy y los siguientes ciclos esperan el resultado. Una máquina de estados permite coordinar esa
secuencia sin detener la tarea.

CASE eState OF
E_State.Idle:

![Recurso gráfico de la página 21](assets_v2/imagen_3cc17fd9854ed353.jpeg)


<!-- Página PDF 22 -->

IF bStart THEN eState := E_State.Starting; END_IF

E_State.Starting:
bCommand := TRUE;
IF bReady THEN eState := E_State.Running; END_IF

E_State.Running:
bCommand := FALSE;
IF bStop THEN eState := E_State.Idle; END_IF
END_CASE;
Qué hace y cómo funciona. Cada ciclo ejecuta sólo la rama del estado actual. Las transiciones cambian
eState cuando se cumplen condiciones. No hay esperas bloqueantes; el programa vuelve a evaluarse en el
ciclo siguiente.


<!-- Página PDF 23 -->

## 11. Temporizadores, flancos y biblioteca Tc2_Standard

Las librerías estándar proporcionan bloques ampliamente usados para lógica temporal y
detección de cambios. TON, TOF, R_TRIG y F_TRIG son herramientas esenciales.

### 11.1 TON: retardo a la conexión

TON coloca Q en TRUE cuando IN ha permanecido TRUE durante PT. ET informa el tiempo transcurrido.
Si IN vuelve a FALSE antes de cumplir PT, el temporizador se reinicia.

TON: temporizador de retardo a la conexión.

VAR
fbDelay : TON;
END_VAR

fbDelay(IN := bSensor, PT := T#2S);
bConfirmed := fbDelay.Q;
Qué hace y cómo funciona. El bloque se llama cada ciclo. Si bSensor permanece activo durante 2
segundos, Q pasa a TRUE y bConfirmed también. Si el sensor se apaga antes, el conteo vuelve a comenzar
la próxima vez.

### 11.2 Flanco ascendente

R_TRIG produce un pulso de un solo ciclo cuando su entrada cambia de FALSE a TRUE. Esto es ideal para
contar pulsaciones o disparar una acción sólo una vez.

![Recurso gráfico de la página 23](assets_v2/imagen_1e3a0bfe9f7191f4.jpeg)


<!-- Página PDF 24 -->

R_TRIG detecta el cambio FALSE -> TRUE.

VAR
fbStartEdge : R_TRIG;
END_VAR

fbStartEdge(CLK := bStartButton);
IF fbStartEdge.Q THEN
nStarts := nStarts + 1;
END_IF;
Qué hace y cómo funciona. Mantener pulsado el botón durante varios ciclos no incrementa
repetidamente el contador: Q sólo es TRUE durante el ciclo del flanco ascendente.

![Recurso gráfico de la página 24](assets_v2/imagen_d2297f358b5506fc.jpeg)


<!-- Página PDF 25 -->

## 12. Entradas/salidas, Process Image y EtherCAT

La lógica PLC se vuelve útil cuando se conecta al proceso. TwinCAT organiza dispositivos en el
árbol de I/O y permite vincular variables del software con datos de proceso del hardware.

### 12.1 Del sensor a la variable

Una entrada física cambia en un terminal de E/S. El bus de campo transporta el dato al master. TwinCAT
lo incorpora al proceso de E/S y una variable PLC enlazada puede utilizarlo. En sentido contrario, una
variable de salida produce un dato que finalmente llega al actuador.

Este mecanismo explica por qué un nombre como bStartSensor en el código no “conoce” por sí mismo el
terminal físico: debe existir una vinculación con el canal correspondiente.

Vinculación entre variables de software y canales de hardware.

### 12.2 EtherCAT

EtherCAT es un bus Ethernet industrial ampliamente utilizado en el ecosistema Beckhoff. Un EtherCAT
Master coordina slaves como terminales de E/S, drives u otros dispositivos. TwinCAT puede implementar
el master por software y sincronizar intercambio de datos con tareas de tiempo real.

Distributed Clocks permite una referencia temporal distribuida de alta precisión entre dispositivos
compatibles, relevante en motion, adquisición sincronizada y otras aplicaciones exigentes.

![Recurso gráfico de la página 25](assets_v2/imagen_2aa6e2cd26595cb0.jpeg)


<!-- Página PDF 26 -->

El fieldbus conecta el controlador con dispositivos distribuidos de proceso.

### 12.3 Práctica segura de mapeo

Para practicar, crea variables con atributos de entrada/salida o enlázalas desde el árbol de I/O, observa el
icono/estado de enlace y comprueba que el tipo y tamaño sean compatibles. Antes de activar una salida
real, identifica el actuador, su estado seguro y cualquier interbloqueo.

VAR_GLOBAL
bSensor AT %I* : BOOL;
bLamp AT %Q* : BOOL;
END_VAR
Qué hace y cómo funciona. La sintaxis %I* y %Q* declara variables asociables al área de entradas y
salidas. El asterisco deja que la dirección concreta se resuelva mediante la configuración/enlace del
proyecto en lugar de codificar una dirección fija.

![Recurso gráfico de la página 26](assets_v2/imagen_115963d8e8857296.jpeg)


<!-- Página PDF 27 -->

## 13. Librerías, utilidades y reutilización de software

Las librerías evitan duplicar código y permiten distribuir componentes con versión, namespace
y dependencias controladas.

### 13.1 Library Manager

El objeto References/Library Manager permite integrar y gestionar PLC libraries. En un proyecto
profesional es útil revisar qué bibliotecas están presentes, qué versiones se resuelven y si existen
placeholders.

Una librería propia suele extraer bloques reutilizables del programa principal, definir metadatos y
versión, compilarse e instalarse para poder referenciarla desde otros proyectos.

Las librerías permiten reutilizar funcionalidad entre proyectos.

### 13.2 Tc2_Utilities y estructuras de datos

Tc2_Utilities contiene utilidades de sistema y bloques como FB_MemRingBuffer. Un ring buffer reutiliza
una región de memoria para almacenar elementos en orden, útil para colas de eventos o telemetría.

![Recurso gráfico de la página 27](assets_v2/imagen_a137cae8ae690957.jpeg)


<!-- Página PDF 28 -->

Concepto de buffer circular empleado por FB_MemRingBuffer.

Idea clave: Las librerías aportan reutilización, pero también dependencias. Para reproducibilidad conviene
controlar versiones y documentar los componentes de los que depende la aplicación.

![Recurso gráfico de la página 28](assets_v2/imagen_0558847f70cb21c1.jpeg)


<!-- Página PDF 29 -->

## 14. Diagnóstico, online, cambios y buenas prácticas de puesta en marcha

TwinCAT ofrece herramientas para observar valores, forzar, trazar referencias y diagnosticar.
El reto no es sólo conocerlas, sino usarlas sin convertir el diagnóstico en un riesgo operativo.

### 14.1 Monitorización y Watch

En modo online el editor puede mostrar valores actuales. Las Watch Lists ayudan a reunir variables de
distintos POUs. Cross Reference permite localizar lecturas y escrituras de una variable. Breakpoints y
stepping son útiles en escenarios controlados, pero detener lógica de una máquina real puede ser
peligroso.

### 14.2 Forcing

Forzar una variable hace que el entorno imponga un valor incluso si la lógica intentaría escribir otro. Es
útil para pruebas, pero puede anular condiciones normales del programa. Mantén un registro claro de
fuerzas activas y elimínalas al terminar.

### 14.3 Online Change y Reset

Online Change busca transferir modificaciones compatibles conservando el estado de la aplicación.
Cambios estructurales pueden requerir descarga completa o reinicio. Reset cold y reset origin tienen
impactos diferentes sobre variables y datos persistentes/retain según su configuración.

La documentación Beckhoff incluye una reserva de memoria configurable para Online Change de
Function Blocks, lo que muestra que la capacidad de cambiar una aplicación en ejecución también tiene
implicaciones de memoria y layout.

### 14.4 Checklist de puesta en marcha

Antes de activar: compila sin errores, revisa target y rutas, verifica E/S enlazadas, confirma estados
seguros, identifica qué variables pueden moverse físicamente y dispone de una forma de detener el
proceso. Después de activar: revisa task load, errores de bus, estados de dispositivos y comportamiento
online.


<!-- Página PDF 30 -->

## 15. ADS: comunicación entre TwinCAT y aplicaciones externas

Automation Device Specification (ADS) es una interfaz independiente del dispositivo/bus que
permite comunicación entre componentes TwinCAT y clientes externos.

### 15.1 Modelo cliente-servidor

Los módulos TwinCAT pueden verse como dispositivos ADS que proporcionan servicios. Un cliente
solicita leer, escribir o recibir notificaciones. El direccionamiento combina AmsNetId y puerto ADS; el
AmsNetId identifica el nodo TwinCAT y no debe confundirse con una dirección IP.

ADS permite que clientes y servidores intercambien datos dentro o fuera del equipo.

### 15.2 Router y rutas

El ADS Message Router encamina mensajes hacia el dispositivo/puerto correcto. Para comunicación
remota se configuran rutas entre nodos. Una ruta correcta, el AmsNetId adecuado y el estado del runtime
son requisitos habituales antes de culpar al código cliente.

![Recurso gráfico de la página 30](assets_v2/imagen_1530aecf400f7a1c.jpeg)


<!-- Página PDF 31 -->

Un mensaje AMS/ADS contiene información de direccionamiento y comando.

### 15.3 Patrón de integración

Una aplicación HMI, servicio .NET o herramienta de análisis puede conectarse al PLC, resolver un
símbolo y leer/escribir su valor. Para datos periódicos suele ser más eficiente usar notificaciones que
realizar lecturas agresivas sin necesidad.

En producción considera permisos, Secure ADS cuando corresponda, exposición mínima de símbolos y
manejo robusto de reconexiones.

![Recurso gráfico de la página 31](assets_v2/imagen_8566fc85be5d7e4d.jpeg)


<!-- Página PDF 32 -->

## 16. TwinCAT Functions y Automation Interface

El núcleo PLC es sólo una parte del ecosistema. TwinCAT Functions amplían capacidades y
Automation Interface permite automatizar tareas de ingeniería.

### 16.1 TwinCAT Functions

Las TwinCAT Functions añaden módulos para HMI, medición, motion, conectividad, visión y otras áreas.
Ejemplos del material son OPC UA, Modbus TCP, PROFINET o interfaces JSON. Su instalación puede
incorporar componentes de runtime, objetos de configuración y PLC libraries.

Las TwinCAT Functions amplían la plataforma con tecnologías específicas.

### 16.2 Automation Interface

TwinCAT Automation Interface expone una API para manipular configuraciones desde herramientas
externas, habitualmente junto con la automatización de Visual Studio/DTE. Permite crear o abrir
soluciones, modificar el árbol TwinCAT, configurar targets o preparar procesos repetibles.

Su valor aumenta en entornos con muchas máquinas, generación automática de configuraciones o
integración CI/CD. Automatizar no elimina la necesidad de validar: simplemente convierte pasos
manuales en un proceso reproducible.

![Recurso gráfico de la página 32](assets_v2/imagen_2dffe340ac3d6cd2.jpeg)


<!-- Página PDF 33 -->

Automation Interface permite controlar tareas de ingeniería desde software externo.

![Recurso gráfico de la página 33](assets_v2/imagen_d32bd92d4d8740f7.jpeg)


<!-- Página PDF 34 -->

## 17. Versionado, compatibilidad y pruebas automatizadas

El software PLC se beneficia de las mismas prácticas de ingeniería que otros sistemas: historial
de cambios, versiones reproducibles, pruebas y automatización.

### 17.1 Git y TwinCAT

Git registra cambios, permite ramas y facilita colaboración. Un flujo básico usa working directory, staging
area, commit local y repositorio remoto. Los archivos generados o dependientes de máquina que no
deban versionarse se excluyen mediante .gitignore.

Antes de aceptar un merge, compila y prueba. Un conflicto resuelto sintácticamente no garantiza que la
lógica combinada sea correcta.

Control de versiones: historial, colaboración y trazabilidad.

### 17.2 Versiones de TwinCAT y dependencias

Abrir el mismo proyecto con builds o librerías distintas puede producir resultados de compilación
diferentes. TwinCAT Remote Manager ayuda a trabajar con toolsets/versiones concretas; además
conviene fijar versiones de librerías/placeholders cuando la reproducibilidad sea importante.

### 17.3 TDD y TcUnit

Test-Driven Development sigue el ciclo Red -> Green -> Refactor: primero se expresa un comportamiento
mediante una prueba que falla, luego se implementa lo mínimo para aprobarla y finalmente se mejora el
diseño manteniendo las pruebas verdes. TcUnit es un framework de unit testing para TwinCAT
mencionado en el material.

![Recurso gráfico de la página 34](assets_v2/imagen_c425986dcd367edf.jpeg)


<!-- Página PDF 35 -->

Ciclo conceptual de desarrollo dirigido por pruebas.

TEST('Counter increments once');
AssertEquals_DINT(
Expected := 1,
Actual := fbCounter.GetValue()
);
Qué hace y cómo funciona. El ejemplo es deliberadamente esquemático: una prueba expresa una
expectativa sobre el comportamiento del objeto. En TcUnit real, la suite, la inicialización y el assertion
concreto dependen de la versión/API instalada. La idea central es automatizar una condición verificable y
repetible.

![Recurso gráfico de la página 35](assets_v2/imagen_f89ad8b921df9371.jpeg)


<!-- Página PDF 36 -->

## 18. Proyecto integrador guiado

Para cerrar, construiremos mentalmente una estación pequeña: un sensor detecta una pieza,
un pulsador habilita el sistema, una salida representa un actuador y un temporizador detecta si
el proceso tarda demasiado.

### 18.1 Requisitos

El sistema debe contar sólo un flanco por pieza. Cuando está habilitado y llega una pieza, activa una
salida durante un tiempo breve. Si la salida permanece activa más de 2 segundos se genera una alarma.
El contador y la alarma deben observarse online.

PROGRAM MAIN
VAR
bEnable     : BOOL;
bPartSensor  : BOOL;
bActuator    : BOOL;
bTimeout     : BOOL;
nParts      : UDINT;
fbPartEdge   : R_TRIG;
fbMaxTime    : TON;
END_VAR

fbPartEdge(CLK := bPartSensor);

IF bEnable AND fbPartEdge.Q THEN
nParts := nParts + 1;
bActuator := TRUE;
END_IF;

fbMaxTime(IN := bActuator, PT := T#2S);
bTimeout := fbMaxTime.Q;

IF NOT bEnable OR bTimeout THEN
bActuator := FALSE;
END_IF;
Qué hace y cómo funciona. R_TRIG transforma la detección de la pieza en un pulso de un ciclo para que
nParts aumente sólo una vez. TON vigila cuánto tiempo permanece activo el actuador. Si supera 2 s,
bTimeout se activa y la última condición deshabilita la salida. El ejemplo integra ejecución cíclica, flancos,
temporización y lógica de seguridad básica.

### 18.2 Cómo probarlo sin hardware

Pon bEnable en TRUE desde el entorno online. Cambia bPartSensor de FALSE a TRUE y vuelve a FALSE: el
contador debe subir una vez. Mantén el actuador activo y observa ET/Q del temporizador. Después repite
deshabilitando bEnable.


<!-- Página PDF 37 -->

Cuando el comportamiento sea correcto con variables internas, sustituye las señales simuladas por
variables enlazadas a E/S reales. Haz ese paso sólo con el equipo en condiciones seguras.

### 18.3 Cómo evolucionar este ejemplo

El siguiente nivel sería encapsular el actuador en un FB, reemplazar BOOL dispersos por una máquina de
estados, registrar eventos de timeout en un buffer, exponer diagnóstico por ADS y añadir pruebas
unitarias para la lógica de conteo.


<!-- Página PDF 38 -->

## 19. Glosario y ruta de aprendizaje

Este último capítulo reúne términos que aparecen de forma recurrente y propone un orden
razonable para continuar estudiando.

Término                                        Definición breve

Program Organization Unit: programa, función o POU
bloque de función.
Data Unit Type: tipo definido por el usuario, por DUT
ejemplo STRUCT o ENUM.
GVL                                             Global Variable List.
ST                                               Structured Text, lenguaje textual IEC 61131-3.
XAE                                          Entorno de ingeniería TwinCAT.
XAR                                       Runtime de automatización TwinCAT.
Unidad planificada que ejecuta código con un Task
ciclo/prioridad.
Representación de datos de E/S intercambiados Process Image
con el proceso.
EtherCAT Master                                Controlador de la red EtherCAT.
Mecanismo de sincronización temporal Distributed Clocks
distribuida de EtherCAT.
Automation Device Specification, interfaz de ADS
comunicación TwinCAT.
Identificador de nodo usado en direccionamiento AmsNetId
ADS.
Transferencia compatible de cambios
Online Change                               manteniendo ejecución/estado en determinados
casos.
FB                                             Function Block con estado de instancia.
Contrato de métodos para desacoplar consumidor Interface
e implementación.
Paquete reutilizable de tipos/POUs con versión y Library
dependencias.

### 19.1 Ruta sugerida

Nivel inicial: navegación XAE, build/login/run, ST básico, tipos, IF/CASE/FOR, TON/R_TRIG y
monitorización online.

Nivel intermedio: DUT, arrays, FB/métodos, interfaces, máquinas de estados, E/S y EtherCAT, librerías,
diagnóstico y ADS.


<!-- Página PDF 39 -->

Nivel avanzado: diseño orientado a objetos, task tuning, Distributed Clocks, motion, comunicaciones,
pruebas automatizadas, CI/CD, Automation Interface, análisis estático y arquitectura modular.

Idea clave: No necesitas memorizar cada menú o bloque. Aprende a reconocer el problema, localizar la
documentación apropiada, construir una prueba pequeña y observar el sistema. Esa habilidad escala mucho
mejor que memorizar APIs.


<!-- Página PDF 40 -->

Referencias del material utilizado

La sección de descarga e instalación fue actualizada con el flujo oficial vigente para TwinCAT 3.1 Build
4026 y TwinCAT Package Manager consultado en septiembre de 2026. El resto del tutorial se elaboró a
partir de las transcripciones e imágenes del paquete “Videos TwinCAT 3 procesados” y de la
documentación Beckhoff convertida a Markdown incluida por el usuario. Entre las fuentes técnicas
consultadas se encuentran:

   Beckhoff - Download finder y registro/inicio de sesión myBeckhoff.
   Beckhoff Information System - Installation TwinCAT 3.1 Build 4026 y TwinCAT Package Manager.
   Beckhoff Information System - Setting up the TwinCAT Package Manager.
   Beckhoff Information System - Structured Text (ST), Extended Structured Text (ExST).
   Beckhoff Information System - Programming Structured Text (ST).
   Beckhoff Information System - Declaring variables.
   Beckhoff Information System - ST instruction IF.
   Beckhoff Information System - Task Settings.
   Beckhoff Information System - Library Manager.
   Beckhoff Information System - Distributed Clocks.
   Beckhoff Information System - TwinCAT ADS.
   Beckhoff Information System - Online Change Memory Reserve Settings.
   Serie procesada “PLC programming using TwinCAT 3”, partes sobre introducción, instalación, tareas,
tipos, funciones, FB/interfaces, instrucciones, Tc2_Standard, utilidades, I/O, librerías, TwinCAT
Functions, Git, versiones, ADS, Automation Interface y TDD.

Nota: las capacidades, menús, nombres de paquetes, requisitos y APIs pueden variar entre builds de
TwinCAT 3 y versiones de librerías. Para un proyecto productivo se debe contrastar el detalle específico
con la documentación correspondiente a la versión instalada.
