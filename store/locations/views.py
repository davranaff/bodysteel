from rest_framework import status, viewsets
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response

from store.models import Filial, FilialPhoto
from store.serializers.filiales import FilialSerializer


class FilialViewSet(viewsets.ModelViewSet):
    queryset = Filial.objects.prefetch_related('photos').all()
    serializer_class = FilialSerializer

    def get_permissions(self):
        if self.action in {'list', 'retrieve'}:
            return [AllowAny()]
        return [IsAdminUser()]

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return Response({'data': serializer.data}, status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object())
        return Response({'data': serializer.data}, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'data': serializer.data}, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            self.get_object(),
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'data': serializer.data}, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'data': serializer.data}, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        self.get_object().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def add_photos(self, request, pk=None):
        filial = self.get_object()
        images = request.FILES.getlist('photos') or request.FILES.getlist('new_photos')
        if not images:
            return Response(
                {'errors': {'photos': ['Передайте минимум одно фото для загрузки.']}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for image in images:
            FilialPhoto.objects.create(filial=filial, photo=image)

        serializer = self.get_serializer(filial)
        return Response({'data': serializer.data}, status=status.HTTP_200_OK)

    def delete_photo(self, request, pk=None, photo_id=None):
        filial = self.get_object()
        get_object_or_404(filial.photos, pk=photo_id).delete()
        serializer = self.get_serializer(filial)
        return Response({'data': serializer.data}, status=status.HTTP_200_OK)
