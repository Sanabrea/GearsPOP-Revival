# Protocolo Catapult (Gears POP! 1.98)

Transporte: gRPC duplex `/GrpcTransport/raw` (`byte[]` ↔ `byte[]`), un stream por canal (login 12000, gateway 12345).
Cada mensaje gRPC lleva un `Catapult.Protocol.Message` serializado con **protobuf-net** y herencia (`ProtoInclude`).

## Envoltura
```
Message {
  1: Headers        repetido MessageHeader
  <etiqueta>: cuerpo del subtipo (Message<T> o Result<T>), ver message_tags.tsv
}
MessageHeader { <etiqueta del subtipo>: ... }
  51110556 OperationHeader    { 1: RequestId (bcl.Guid {1: fixed64 lo, 2: fixed64 hi}), 2: Type (1 OneWay, 2 Request, 3 Reply) }
  31685340 CorrelationHeader  { 1: ActivityId (Guid) }
  2056396  UserSessionHeader
  60349934 TraceHeader
  72409651 TimeModifierHeader
  89108981 TimestampHeader (por descarte)
Message<T>  { 1: Body }
Result<T>   { 1: Body, 2: Error (ErrorDescription { 1: Code uint16, 2: string, 3: string, 4: ... }) }
```
protobuf-net escribe primero el subtipo y después los campos de la base; el orden no importa al leer.

## Login (puerto 12000)
- Petición: `Message<LoginRequest>` = **71269765**. `LoginRequest` { 1 IdentityType ("DeviceId"), 2 IdentityToken (88 caracteres),
  3 ClientVersion, 4 ContentETag, 5 Platform, 6 UserParameters (mapa), 7 Properties (mapa) }.
- Respuesta: `Result<SessionTokenResponse>` = **15174312**. `SessionTokenResponse` { 1 SessionToken, 2 AccountId, 3 Roles (repetido),
  4 ContentUrl, 5 ContentVersion, 6 ContentEtag, 7 AnalyticsId (obsoleto), 8 ExtraIdentities (mapa) },
  con `OperationHeader { RequestId = el de la petición, Type = Reply }`.

## Cómo se sacó
- `scripts/proto_tags.py <dump> <libil2cpp.so> <RVA de GeneratedProtoSerializer.Write(T)>`: etiqueta → clase, siguiendo la cascada
  de comparaciones de clase (punteros resueltos con las relocaciones `R_AARCH64_RELATIVE`). Faltan algunas `Message<T>`
  (las de comprobación por jerarquía); `Message<LoginRequest>` se resolvió a mano.
- `scripts/proto_fields.py`: números de campo de cada `Write(T)`. El orden de los getters indica qué propiedad es cada campo.
- RVAs de los `Write(T)`: buscar `static void Write(<Tipo> ,` en `analysis/il2cpp_dump/dump.cs`.

## Contenido (CMS) al iniciar sesión
Si `LoginRequest.ContentETag` no coincide con el ETag del servidor, la respuesta lleva `Result.Error = { 1: 471 ContentUpdateRequired }`
junto con `Body.ContentUrl/ContentEtag/ContentVersion`. El cliente (`ContentUpdateStep`) descarga `ContentUrl`, guarda el ETag
y repite el login. Sin caché del CMS (`files/content_data`), el cliente se desconecta al entrar al gateway.
