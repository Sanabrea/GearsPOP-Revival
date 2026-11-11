# Catapult protocol (Gears POP! 1.98)

Transport: gRPC duplex `/GrpcTransport/raw` (`byte[]` ↔ `byte[]`), one stream per channel (login 12000, gateway 12345).
Each gRPC message carries a `Catapult.Protocol.Message` serialized with **protobuf-net** and inheritance (`ProtoInclude`).

## Envelope
```
Message {
  1: Headers        repeated MessageHeader
  <tag>: subtype body (Message<T> or Result<T>), see message_tags.tsv
}
MessageHeader { <subtype tag>: ... }
  51110556 OperationHeader    { 1: RequestId (bcl.Guid {1: fixed64 lo, 2: fixed64 hi}), 2: Type (1 OneWay, 2 Request, 3 Reply) }
  31685340 CorrelationHeader  { 1: ActivityId (Guid) }
  2056396  UserSessionHeader
  60349934 TraceHeader
  72409651 TimeModifierHeader
  89108981 TimestampHeader (by elimination)
Message<T>  { 1: Body }
Result<T>   { 1: Body, 2: Error (ErrorDescription { 1: Code uint16, 2: string, 3: string, 4: ... }) }
```
protobuf-net writes the subtype first and then the base fields; order does not matter when reading.

## Login (port 12000)
- Request: `Message<LoginRequest>` = **71269765**. `LoginRequest` { 1 IdentityType ("DeviceId"), 2 IdentityToken (88 characters),
  3 ClientVersion, 4 ContentETag, 5 Platform, 6 UserParameters (map), 7 Properties (map) }.
- Response: `Result<SessionTokenResponse>` = **15174312**. `SessionTokenResponse` { 1 SessionToken, 2 AccountId, 3 Roles (repeated),
  4 ContentUrl, 5 ContentVersion, 6 ContentEtag, 7 AnalyticsId (obsolete), 8 ExtraIdentities (map) },
  with `OperationHeader { RequestId = the request's one, Type = Reply }`.

## How it was obtained
- `scripts/proto_tags.py <dump> <libil2cpp.so> <RVA of GeneratedProtoSerializer.Write(T)>`: tag → class, following the cascade
  of class comparisons (pointers resolved with the `R_AARCH64_RELATIVE` relocations). Some `Message<T>` are missing
  (those checked via hierarchy); `Message<LoginRequest>` was resolved by hand.
- `scripts/proto_fields.py`: field numbers of each `Write(T)`. The order of the getters indicates which property each field is.
- RVAs of the `Write(T)`: search for `static void Write(<Type> ,` in `analysis/il2cpp_dump/dump.cs`.

## Content (CMS) at login
If `LoginRequest.ContentETag` does not match the server's ETag, the response carries `Result.Error = { 1: 471 ContentUpdateRequired }`
together with `Body.ContentUrl/ContentEtag/ContentVersion`. The client (`ContentUpdateStep`) downloads `ContentUrl`, stores the ETag
and repeats the login. Without the CMS cache (`files/content_data`), the client disconnects when entering the gateway.
