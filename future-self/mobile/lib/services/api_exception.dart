class ApiException implements Exception {
  final String message;
  final int? statusCode;
  final dynamic data;

  ApiException(this.message, {this.statusCode, this.data});

  @override
  String toString() => 'ApiException: $message (Status: $statusCode)';

  bool get isServerError => statusCode != null && statusCode! >= 500;
  bool get isClientError => statusCode != null && statusCode! >= 400 && statusCode! < 500;
  bool get isNetworkError => statusCode == null;

  static ApiException fromHttpError(dynamic error) {
    if (error is ApiException) return error;
    
    return ApiException(
      error.toString(),
      statusCode: error is int ? error : null,
      data: error is Map ? error : null,
    );
  }
}

class NetworkTimeoutException extends ApiException {
  NetworkTimeoutException([super.message = 'Network request timed out']);
}

class ServerException extends ApiException {
  ServerException(super.message, {super.statusCode, super.data});
}

class ClientException extends ApiException {
  ClientException(super.message, {super.statusCode, super.data});
}